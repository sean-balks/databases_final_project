from flask import Flask, render_template, request, session, url_for, redirect
import pymysql
import hashlib
from functools import wraps
import datetime

app = Flask(__name__)
app.secret_key = "secret key"

conn = pymysql.connect(host='localhost',
                       user='root',
                       password='',
                       db='project',
                       charset='utf8mb4',
                       port=3306,
                       cursorclass=pymysql.cursors.DictCursor,
                       autocommit=True)


def require_cust_login(f):
    @wraps(f)
    def checkLoginStatus(*args, **kwargs):
        if not "Username" in session:  # if they're not logged in, make them login
            return redirect(url_for("login"))
        elif session["userType"] != "customer":
            userType = session["userType"]
            if userType == "staff":
                return redirect(url_for("staff"))
        return f(*args, **kwargs)
    return checkLoginStatus


def require_staff_login(f):
    @wraps(f)
    def checkLoginStatus(*args, **kwargs):
        if not "Username" in session:  # if they're not logged in, make them login
            return redirect(url_for("login"))
        elif session["userType"] != "staff":
            userType = session["userType"]
            if userType == "customer":
                return redirect(url_for("customer"))
        return f(*args, **kwargs)
    return checkLoginStatus


@app.route('/')
def hello():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    cursor = conn.cursor()

    if request.method == 'POST':
        #check if they already have credentials in the DB
        hexHashPass = hashlib.md5(request.form['Password'].encode()).hexdigest()
        customerQuery = "select * from Customer where customer_email = \"" + request.form['Username'] + "\" AND password = \"" \
                        + hexHashPass + "\""
        staffQuery = "select * from Staff where username = \"" + request.form['Username'] + "\" AND password = \"" \
                        + hexHashPass + "\""

        if cursor.execute(customerQuery):  # successful login attempt for customer
            session["Username"] = request.form["Username"]
            session["userType"] = "customer"
            cursor.close()
            return redirect(url_for('customer'))
        elif cursor.execute(staffQuery):  # successful login attempt for staff
            session["Username"] = request.form["Username"]
            session["userType"] = "staff"

            query = f'''select airline_name from Staff where username = \'{session["Username"]}\''''
            cursor.execute(query)
            airline_name = cursor.fetchone()['airline_name']
            session['airline_name'] = airline_name

            cursor.close()
            return redirect(url_for('staff'))
        else:
            error = "Invalid username and/or password. Please enter correct credentials."
    cursor.close()
    return render_template('index.html', error=error)


@app.route("/customer")
@require_cust_login
def customer():
    return render_template("customer.html")


@app.route("/staff")
@require_staff_login
def staff():
    return render_template("staff.html")


@app.route("/registerCustomer", methods=['GET','POST'])
def registerCustomer():
    error = None
    if request.method == "POST":
        cursor = conn.cursor()
        query = "select * from Customer where customer_email = \"" + request.form['cust_email'] + '\"'
        if cursor.execute(query):
            error = "Account with email already exists, please use a different email"
            return render_template("index.html", error=error)
        passHash = request.form['cust_password']
        hashedPass = hashlib.md5(passHash.encode())
        hexHashPass = hashedPass.hexdigest()
        query = f'''INSERT INTO Customer VALUES (\'{request.form['cust_name']}\', \'{request.form['cust_email']}\', 
                \'{hexHashPass}\', {request.form['cust_build_num']}, \'{request.form['cust_street']}\', 
                \'{request.form['cust_city']}\', \'{request.form['cust_state']}\', {request.form['cust_phone_number']}, {request.form['cust_passport_number']},
                \'{request.form['cust_passport_expiration']}\', \'{request.form['cust_passport_country']}\', \'{request.form['cust_dob']}\')'''
        if cursor.execute(query):
            cursor.close()
            return redirect(url_for('login'))
    return render_template("customer.html", error=error)


@app.route("/registerStaff", methods=['GET','POST'])
def registerStaff():
    error = None
    if request.method == "POST":
        cursor = conn.cursor()
        query = "select * from Staff where username = \"" + request.form['staff_username'] + '\"'
        if cursor.execute(query):
            error = "Account with username already exists, please use a different username"
            return render_template("index.html", error=error)

        passHash = request.form['staff_password']
        hashedPass = hashlib.md5(passHash.encode())
        hexHashPass = hashedPass.hexdigest()
        query = f'''INSERT INTO Staff VALUES (\'{request.form['staff_username']}\', \'{hexHashPass}\',  
                \'{request.form['staff_first_name'] + " " + request.form['staff_last_name']}\', \'{request.form['staff_email']}\', \'{request.form['staff_dob']}\', \'{request.form['staff_airline']}\')'''
        if cursor.execute(query):

            numbers = [request.form['staff_phone_number']]
            numbers.extend(request.form["staff_additional_phone_number"].split(", "))
            for num in numbers:
                query = f'''insert into StaffPhones values (\'{request.form['staff_username']}\', {num})'''
                cursor.execute(query)

            cursor.close()
            return redirect(url_for('login'))
    return render_template("staff.html", error=error)


@app.route("/customerFlight", methods=["GET"])
@require_cust_login
def customerFlights():
    cursor = conn.cursor()
    query = "select ticket_id from Purchases where customer_email = \"" + session['Username'] + "\""
    cursor.execute(query)
    ticketIDs = cursor.fetchall()
    query = "select flight_number from Ticket where ticket_id = "
    for ticket in ticketIDs:
        query += str(ticket.get('ticket_id'))
        query += " or ticket_id = "
    query += " -1 "
    cursor.execute(query)
    flight_nums = cursor.fetchall()
    query = "select * from Flight where (CURRENT_DATE < Flight.departure_date OR (CURRENT_DATE = Flight.departure_date " \
            "AND CURRENT_TIME < departure_time)) and (flight_number = "
    for flight in flight_nums:
        query += str(flight.get("flight_number")) + " or flight_number = "
    query += " -1) "
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()
    return render_template("customer.html", results=results)


@app.route("/staffflights", methods=["GET"])
@require_staff_login
def staffFlights():
    cursor = conn.cursor()
    query = "select airline_name from Staff where username = \"" + session['Username'] + "\""
    cursor.execute(query)
    airlineName = cursor.fetchone().get("airline_name")
    query = "select * from Flights where airline_name = \"" + airlineName + "\""
    cursor.execute(query)

    customer_list = []

    query = f"Select flight_number from Flight where airline_name = \'{airlineName}\' and ((CURRENT_DATE < " \
            f"Flight.departure_date) OR (CURRENT_TIME < departure_time AND CURRENT_DATE = Flight.departure_date)) and" \
            f"(Flight.departure_date < ADDDATE(CURRENT_DATE, INTERVAL 30 DAY))"

    cursor.execute(query)
    flightNums = cursor.fetchall()
    query = "select * from Flight where flight_number = "
    for flight in flightNums:
        query += str(flight.get('flight_number')) + " or flight_number ="
    query += " -1 "
    cursor.execute(query)
    results = cursor.fetchall()
    for number in flightNums:
        curr_num = number.get("flight_number")
        query = f'''SELECT Customer.name from Ticket NATURAL JOIN Purchases NATURAL JOIN Customer where Ticket.flight_number = {curr_num}'''
        cursor.execute(query)
        cust_names = cursor.fetchall()
        list_of_names = []
        for name in cust_names:
            curr_name = name.get("name")
            list_of_names.append(curr_name)
        customer_list.append(list_of_names)
    cursor.close()

    return render_template("staff.html", results=results, customers=customer_list)


@app.route("/addairport", methods=["GET", "POST"])
@require_staff_login
def addAirport():
    error = None
    if request.method == "POST":
        cursor = conn.cursor()
        query = f'''insert into Airport values (\'{request.form['airport_name']}\', \'{request.form['source_city']}'''
        cursor.execute(query)
        cursor.close()
    return render_template("staff.html", error=error)


@app.route("/addairplane", methods=["GET", "POST"])
@require_staff_login
def addAirplane():
    error = None
    if request.method == "POST":
        cursor = conn.cursor()
        query = f'''insert into Airplane values (\'{request.form['airplane_ID']}\', \'{request.form['num_of_seats']}\', \'{request.form['airline_name']}'''
        cursor.execute(query)
        cursor.close()
    return render_template("staff.html", error=error)


@app.route("/addflight", methods=["GET", "POST"])
@require_staff_login
def addFlight():
    error = None
    if request.method == "POST":
        status = request.form["new_status"]
        if status == "ontime":
            status = "On Time"
        else:
            status = "Delayed"
        cursor = conn.cursor()
        query = f'''insert into Flight values (\'{session['airline_name']}\', \'{status}\', \'{request.form['flight_num']}\', \'{request.form['source_city']}\', \'{request.form['departure_date']}\', 
                \'{request.form['departure_time']}\', \'{request.form['dest_city']}\', \'{request.form['return_date']}\', \'{request.form['return_time']}\', \
                \'{request.form['base_price']}\', \'{request.form['airplane_ID']}'''
        cursor.execute(query)
        cursor.close()
    return render_template("staff.html", error=error)


@app.route("/changestatus", methods=["GET", "POST"])
@require_staff_login
def changeStatus():
    error = None
    if request.method == "POST":
        cursor = conn.cursor()
        status = request.form["new_status"]
        if status == "ontime":
            status = "On Time"
        else:
            status = "Delayed"
        query = f'''update Flight set status = \'{status}\' where flight_number = \'{request.form['flight_num']}\' and departure_date = \'{request.form['departure_date']}\' and departure_time = \'{request.form['departure_time']}\''''
        cursor.execute(query)
        cursor.close()
    return render_template("staff.html", error=error)


@app.route("/frequentfliers")
@require_staff_login
def frequentFliers():
    cursor = conn.cursor()

    freq_dict = {}
    results = []
    flights = []

    date = datetime.datetime.now() - datetime.timedelta(days=365)
    query = f'''SELECT customer_email, count(ticket_id) FROM Purchases NATURAL JOIN Ticket WHERE airline_name = \'{session['airline_name']}\' AND purchase_date >= \'{date.strftime("%Y-%m-%d")}\' group by customer_email order by count(ticket_id) desc limit 5'''
    cursor.execute(query)
    # populate dictionary with customer email as key and number of tickets purchased as value
    for elem in cursor.fetchall():
        freq_dict[elem.get("customer_email")] = elem.get('count(ticket_id)')
    for cust_email in freq_dict.keys():
        query = f'''SELECT * from Customer where customer_email = \'{cust_email}\''''
        cursor.execute(query)
        result = cursor.fetchall()
        results.append(result)

    # Get data on the specific flights
    for flier in results:
        email = flier[0].get('customer_email')
        query = f'''SELECT flight_number from Ticket natural join Purchases where airline_name = \'{session['airline_name']}\' and customer_email = \'{email}\''''
        cursor.execute(query)
        flight_list = cursor.fetchall()
        flights.append(flight_list)
    cursor.close()
    return render_template("staff.html", results=results, flights=flights)


@app.route('/logout', methods=["GET"])
def logout():
    session.pop('Username')
    return render_template("index.html", error="Successfully logged out")


if __name__ == "__main__":
    app.run('127.0.0.1', 5000, debug=True)