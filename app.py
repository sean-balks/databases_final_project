from flask import Flask, render_template, request, session, url_for, redirect
import pymysql
import hashlib
from functools import wraps
import datetime
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

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
        customerQuery = "select * from customer where customer_email = \"" + request.form['Username'] + "\" AND password = \"" \
                        + hexHashPass + "\""
        staffQuery = "select * from staff where username = \"" + request.form['Username'] + "\" AND password = \"" \
                        + hexHashPass + "\""

        if cursor.execute(customerQuery):  # successful login attempt for customer
            session["Username"] = request.form["Username"]
            session["userType"] = "customer"
            cursor.close()
            return redirect(url_for('customer'))
        elif cursor.execute(staffQuery):  # successful login attempt for staff
            session["Username"] = request.form["Username"]
            session["userType"] = "staff"

            query = f'''select airline_name from staff where username = \'{session["Username"]}\''''
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
        query = "select * from customer where customer_email = \"" + request.form['cust_email'] + '\"'
        if cursor.execute(query):
            error = "Account with email already exists, please use a different email"
            return render_template("index.html", error=error)
        passHash = request.form['cust_password']
        hashedPass = hashlib.md5(passHash.encode())
        hexHashPass = hashedPass.hexdigest()
        query = f'''INSERT INTO customer VALUES (\'{request.form['cust_name']}\', \'{request.form['cust_email']}\', 
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
        query = "select * from staff where username = \"" + request.form['staff_username'] + '\"'
        if cursor.execute(query):
            error = "Account with username already exists, please use a different username"
            return render_template("index.html", error=error)

        passHash = request.form['staff_password']
        hashedPass = hashlib.md5(passHash.encode())
        hexHashPass = hashedPass.hexdigest()
        query = f'''INSERT INTO staff VALUES (\'{request.form['staff_username']}\', \'{hexHashPass}\',  
                \'{request.form['staff_first_name'] + " " + request.form['staff_last_name']}\', \'{request.form['staff_dob']}\', \'{request.form['staff_airline']}\')'''
        if cursor.execute(query):

            numbers = [request.form['staff_phone_number']]
            numbers.extend(request.form["staff_additional_phone_number"].split(", "))
            for num in numbers:
                query = f'''insert into staffphones values (\'{request.form['staff_username']}\', {num})'''
                cursor.execute(query)

            cursor.close()
            return redirect(url_for('login'))
    return render_template("staff.html", error=error)


@app.route("/public_search", methods=["GET", "POST"])
def public_search():
    error = None
    cursor = conn.cursor()
    query = ""
    valid = {}
    valid["flight_number"] = request.form['flight_num']
    valid["departure_airport"] = request.form['source_city']
    valid["arrival_airport"] = request.form['dest_city']
    valid["departure_date"] = request.form['departure_date']
    valid["arrival_date"] = request.form['arrival_date']

    query = "select * from flight where "
    for item in valid:
        if valid[item] != "":
            query += item + " = \"" + valid[item] + "\" and "
    query = query[:-5]

    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()

    return render_template("index.html", error=error, results=results)


@app.route("/cancelTrip", methods=["GET", "POST"])
@require_cust_login
def cancelTrip():
    # We assume the cancelled flight is valid and in more than 24 hours
    cursor = conn.cursor()
    ticketID = request.form["ticket_id"]

    # delete the ticket from the purchase table
    deleteQuery = "DELETE FROM purchase WHERE email = \"" + session['Username'] + "\" AND ticket_id = \"" + ticketID + "\""
    if not cursor.execute(deleteQuery):
        error="Unseccessful cancellation. Please try again"
        return render_template("customer.html", error=error)
    conn.commit()
    cursor.close()
    return render_template("customer.html", error="Ticket cancelled successully")


@app.route("/customerSearch", methods=["GET", "POST"])
@require_cust_login
def customerSearch():
    error = None
    cursor = conn.cursor()
    valid = {}
    valid["flight_number"] = request.form['flight_num']
    valid["departure_airport"] = request.form['source_city']
    valid["arrival_airport"] = request.form['dest_city']
    valid["departure_date"] = request.form['departure_date']
    valid["arrival_date"] = request.form['arrival_date']

    query = "select * from flight where "
    for item in valid:
        if valid[item] != "":
            query += item + " = \"" + valid[item] + "\" and "
    query = query[:-5]

    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()

    return render_template("customer.html", error=error, results=results)


@app.route("/customerFlight", methods=["GET"])
@require_cust_login
def customerFlights():
    cursor = conn.cursor()
    query = "select ticket_id from purchases where customer_email = \"" + session['Username'] + "\""
    cursor.execute(query)
    ticketIDs = cursor.fetchall()
    query = "select flight_number from ticket where ticket_id = "
    for ticket in ticketIDs:
        query += str(ticket.get('ticket_id'))
        query += " or ticket_id = "
    query += " -1 "
    cursor.execute(query)
    flight_nums = cursor.fetchall()
    query = "select * from flight where (CURRENT_DATE < flight.departure_date OR (CURRENT_DATE = flight.departure_date " \
            "AND CURRENT_TIME < departure_time)) and (flight_number = "
    for flight in flight_nums:
        query += str(flight.get("flight_number")) + " or flight_number = "
    query += " -1) "
    cursor.execute(query)
    results = cursor.fetchall()
    cursor.close()
    return render_template("customer.html", results=results)


@app.route("/rate", methods=["GET", "POST"])
@require_cust_login
def rateFlight():
    cursor = conn.cursor()
    error = ""
    query = f'''SELECT * FROM purchases NATURAL JOIN ticket NATURAL JOIN flight WHERE customer_email = \'{session['Username']}\' AND arrival_date < CURRENT_DATE()'''
    cursor.execute(query)
    results = cursor.fetchall()
    if request.method == "POST":
        custComment = request.form['comment']
        custRating = request.form['rating']
        flightNum = request.form['flight_num']
        customerEmail = session['Username']


        # We decided to only allow for a customer to rate a flight if they have not done so already
        query = f'''select customer_email, flight_number from rates where customer_email = \'{customerEmail}\' and flight_number = {flightNum}'''
        if cursor.execute(query):
            error = "You already rated this flight!"
        else:
            query = f'''insert into rates values(\"{customerEmail}\", {flightNum}, \"{custComment}\", {custRating})'''
            cursor.execute(query)
            error = "Rate & Comment were Succesful!"
            cursor.close()
    cursor.close()
    return render_template("customer.html", results=results, error=error)


def changeInMonths(date, rotation):
    mon, year = (date.month + rotation) % 12, date.year + (date.month + rotation - 1) // 2
    if not mon: # month is december
        mon = 12
    days_in_mon = [31,28,31,30,31,30,31,31,30,31,30,31]
    day = min(date.day, days_in_mon[mon])
    return date.replace(day=day, month=mon, year=year)


@app.route("/staffflights", methods=["GET"])
@require_staff_login
def staffFlights():
    cursor = conn.cursor()
    query = "select airline_name from staff where username = \"" + session['Username'] + "\""
    cursor.execute(query)
    airlineName = cursor.fetchone().get("airline_name")
    query = "select * from flights where airline_name = \"" + airlineName + "\""
    cursor.execute(query)

    customer_list = []

    query = f"Select flight_number from flight where airline_name = \'{airlineName}\' and ((CURRENT_DATE < " \
            f"flight.departure_date) OR (CURRENT_TIME < departure_time AND CURRENT_DATE = flight.departure_date)) and" \
            f"(flight.departure_date < ADDDATE(CURRENT_DATE, INTERVAL 30 DAY))"

    cursor.execute(query)
    flightNums = cursor.fetchall()
    query = "select * from flight where flight_number = "
    for flight in flightNums:
        query += str(flight.get('flight_number')) + " or flight_number ="
    query += " -1 "
    cursor.execute(query)
    results = cursor.fetchall()
    for number in flightNums:
        curr_num = number.get("flight_number")
        query = f'''SELECT customer.name from ticket NATURAL JOIN purchases NATURAL JOIN customer where ticket.flight_number = {curr_num}'''
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
    error = "Airport added."
    if request.method == "POST":
        cursor = conn.cursor()
        query = f'''insert into airport values (\'{request.form['airport_name']}\', \'{request.form['source_city']}'''
        cursor.execute(query)
        cursor.close()
    return render_template("staff.html", error=error)


@app.route("/addairplane", methods=["GET", "POST"])
@require_staff_login
def addAirplane():
    error = "Airplan added."
    if request.method == "POST":
        cursor = conn.cursor()
        query = f'''insert into airplane values (\'{request.form['airplane_ID']}\', \'{request.form['num_of_seats']}\', \'{request.form['airline_name']}'''
        cursor.execute(query)
        cursor.close()
    return render_template("staff.html", error=error)

# NOT FINISHED YET - Query broken
@app.route("/staffviewflights", methods=["POST"])
@require_staff_login
def staffviewflights():
    cursor = conn.cursor()
    query = "select * from flights where airline = \"" + session['airline_name'] + "\" and departure_date > CURRENT_DATE and departure_date < date_add(now(), interval 30 day)"
    cursor.execute(query)
    results = cursor.fetchall()
    return render_template("staff.html", results=results)

@app.route("/addflight", methods=["GET", "POST"])
@require_staff_login
def addFlight():
    error = "Flight added."
    if request.method == "POST":
        status = request.form["new_status"]
        if status == "ontime":
            status = "On Time"
        else:
            status = "Delayed"
        cursor = conn.cursor()
        query = f'''insert into flight values (\'{session['airline_name']}\', \'{status}\', \'{request.form['flight_num']}\', \'{request.form['source_city']}\', \'{request.form['departure_date']}\', \'{request.form['departure_time']}\', \'{request.form['dest_city']}\', \'{request.form['return_date']}\', \'{request.form['return_time']}\', \'{request.form['base_price']}\', \'{request.form['airplane_ID']}'''
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
        query = f'''update flight set status = \'{status}\' where flight_number = \'{request.form['flight_num']}\' and departure_date = \'{request.form['departure_date']}\' and departure_time = \'{request.form['departure_time']}\''''
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

    date = datetime.now() - datetime.time(days=365)
    query = f'''SELECT customer_email, count(ticket_id) FROM purchases NATURAL JOIN ticket WHERE airline_name = \'{session['airline_name']}\' AND purchase_date >= \'{date.strftime("%Y-%m-%d")}\' group by customer_email order by count(ticket_id) desc limit 5'''
    cursor.execute(query)
    # populate dictionary with customer email as key and number of tickets purchased as value
    for elem in cursor.fetchall():
        freq_dict[elem.get("customer_email")] = elem.get('count(ticket_id)')
    for cust_email in freq_dict.keys():
        query = f'''SELECT * from customer where customer_email = \'{cust_email}\''''
        cursor.execute(query)
        result = cursor.fetchall()
        results.append(result)

    # Get data on the specific flights
    for flier in results:
        email = flier[0].get('customer_email')
        query = f'''SELECT flight_number from ticket natural join purchases where airline_name = \'{session['airline_name']}\' and customer_email = \'{email}\''''
        cursor.execute(query)
        flight_list = cursor.fetchall()
        flights.append(flight_list)
    cursor.close()
    return render_template("staff.html", results=results, flights=flights)


@app.route("/ratings", methods=["POST", "GET"])
@require_staff_login
def ratings():
    cursor = conn.cursor()
    query = "SELECT * from flight where airline_name = \"" + session["airline_name"] + "\""
    cursor.execute(query)
    results = cursor.fetchall()
    if request.method == "POST":
        flight_num = request.form["flight_num"]
        query = "SELECT AVG(`rating`) FROM `rates` WHERE flight_number =" + flight_num
        cursor.execute(query)
        avgRating = cursor.fetchone()["AVG(`rating`)"]
        if not avgRating:
            avgRating = 0
        query = "SELECT customer_email, comment, rating FROM `rates` WHERE flight_number =" + flight_num
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        return render_template("staff.html", average=avgRating, results=results)
    cursor.close()
    return render_template("staff.html", results=results)


@app.route("/reportsDefault", methods=["POST", "GET"])
@require_staff_login
def reportsDefault():
    cursor = conn.cursor()
    airline_name = session["airline_name"]

    today = datetime.datetime.now()


    query = "SELECT COUNT(DISTINCT ticket_id) as count_tix from purchase natural join ticket WHERE customer_email IS NOT NULL AND airline_name = \""+ airline_name +"\" AND DATE(purchase_date) >= DATE_ADD(CURRENT_DATE, INTERVAL -1 MONTH)"

    if not cursor.execute(query):
        last_month = 0
    else:
        last_month = cursor.fetchone()['count_tix']

    year_dict = {}
    year_total = 0
    for mon in range(12):
        query = "SELECT COUNT(DISTINCT ticket_id) as count_tix from purchase natural join ticket WHERE customer_email IS NOT NULL AND airline_name = \""+ airline_name +"\" AND DATE(purchase_date) >= DATE_ADD(DATE(\""+str(today)+"\"), INTERVAL -1 MONTH) AND DATE(purchase_date) <= DATE(\""+str(today)+"\")"
        if cursor.execute(query):
            results = cursor.fetchone()['count_tix']
        else:
            results = 0
        year_total += results
        previous_day = today
        today -= relativedelta(months=1)
        interval = str(today) + ' - ' + str(previous_day)
        year_dict[mon+1] = (interval, results)

    mons = [mon for mon in range(12,0,-1)]
    cursor.close()
    return render_template("defaultReport.html", year_dict=year_dict, last_month=last_month, year_total=year_total, mons=mons)


@app.route("/reports", methods=["POST", "GET"])
@require_staff_login
def reports():
    if request.method == "POST":
        cursor = conn.cursor()
        airline_name = session["airline_name"]

        beg_date = request.form['reportDate1']
        end_date = request.form['reportDate2']

        beg = datetime.date(datetime.strptime(beg_date, "%Y-%m-%d"))
        end = datetime.date(datetime.strptime(end_date, "%Y-%m-%d"))

        num_of_months = (end.year - beg.year) * 12 + (end.month - beg.month)


        query = "SELECT COUNT(DISTINCT ticket_id) as count_tix from purchase natural join ticket WHERE customer_email IS NOT NULL AND airline_name = \""+ airline_name +"\" AND DATE(purchase_date) >= DATE(\""+ str(beg) +"\") AND DATE(purchase_date) <= DATE(\""+ str(end) +"\")"

        if not cursor.execute(query):
            total_tix = 0
        else:
            total_tix = cursor.fetchone()['count_tix']

        year_dict = {}
        for mon in range(12):
            query = "SELECT COUNT(DISTINCT ticket_id) as count_tix from purchase natural join ticket WHERE customer_email IS NOT NULL AND airline_name = \""+ airline_name +"\" AND DATE(purchase_date) <= DATE_ADD(DATE(\""+str(beg)+"\"), INTERVAL 1 MONTH) AND DATE_ADD(DATE(\""+str(beg)+"\"), INTERVAL 1 MONTH) >= DATE(purchase_date)"
            if cursor.execute(query):
                results = cursor.fetchone()['count_tix']
            else:
                results = 0

            previous_day = beg
            beg += relativedelta(months=1)
            interval = str(previous_day) + ' - ' + str(beg)
            year_dict[mon+1] = (interval, results)

        mons = [mon for mon in range(1,num_of_months+1)]
        cursor.close()
        return render_template("report.html", year_dict=year_dict, results=total_tix, mons=mons)
    return render_template("staff.html")



# track monthly wise spending within specified range of dates
@app.route('/specifyspending', methods=["GET", "POST"])
@require_cust_login
def specify_spending():
    if request.method == "POST":
        cursor = conn.cursor()
        date1 = request.form['date1']
        startDate = datetime.date(datetime.strptime(date1, '%Y-%m-%d'))
        date2 = request.form['date2']
        endDate = datetime.date(datetime.strptime(date2, '%Y-%m-%d'))


        num_months = (endDate.year - startDate.year) * 12 + (endDate.month - startDate.month)

        # find the total money spent in range of specified dates
        query = "SELECT SUM(ticket_price) AS total_spent FROM purchase WHERE email = \"" + session['Username'] + \
                "\" AND DATE(purchase_date) >= DATE(\"" + str(startDate) + "\") AND DATE(purchase_date) <= DATE(\"" \
                + str(endDate) + "\")"
        if cursor.execute(query):
            total = cursor.fetchone()['total_spent']
        else:
            total = 0

        # money spent in range by month
        dict = {}
        for mon in range(num_months):
            query = "SELECT SUM(ticket_price) AS total_spent FROM purchase WHERE email = \"" + session['Username'] \
                    + "\" AND DATE(purchase_date) <= DATE_ADD(DATE(\"" + str(startDate) + \
                    "\"), INTERVAL 1 MONTH) AND DATE(purchase_date) >= DATE(\"" + str(startDate) + "\")"
            cursor.execute(query)
            results = cursor.fetchone()['total_spent']
            if not results:
                results = 0
            prev_date = startDate
            startDate += relativedelta(months=1)
            interval = str(prev_date) + ' - ' + str(startDate)
            dict[mon + 1] = (interval, results)


        months = [month for month in range(1, num_months + 1)]
        cursor.close()
        return render_template('spendingRangeResults.html', total=total, dict=dict, months=months)
    return render_template('customer.html')


@app.route("/trackSpending")
@require_cust_login
def trackSpending():
    cursor = conn.cursor()
    # total money spent in the past year
    query = "SELECT SUM(ticket_price) AS total_spent FROM purchase WHERE email = \"" + session['Username'] + \
            "\" AND DATE(purchase_date) >= DATE_ADD(CURRENT_DATE, INTERVAL -1 YEAR)"
    if cursor.execute(query):
        total = cursor.fetchone()['total_spent']
    else:
        total = 0


    # month wise total and total money spent in the last 6 months
    dict = {}
    month_total = 0
    today = datetime.date(datetime.now())
    for mon in range(6):
        query = "SELECT SUM(ticket_price) AS total_spent FROM purchase WHERE email = \"" + session['Username'] + \
                "\" AND DATE(purchase_date) >= DATE_ADD(DATE(\"" + str(today) + \
                "\"), INTERVAL -1 MONTH) AND DATE(purchase_date) <= DATE(\"" + str(today) + "\")"
        cursor.execute(query)
        results = cursor.fetchone()['total_spent']
        if results is not None:
            month_total += results
        else:
            results = 0
        prev_date = today
        today -= relativedelta(months=1)
        interval = str(today) + ' - ' + str(prev_date)
        dict[mon + 1] = (interval, results)
    months = [num for num in range(6, 0, -1)]
    cursor.close()
    return render_template('spendingTrackPage.html.html', total=total, month_total=month_total, dict=dict, months=months)


@app.route("/revenue")
@require_staff_login
def revenue():
    airline_name = session['airline_name']
    cursor = conn.cursor()

    today = datetime.datetime.now()

    one_month_ago = today - datetime.timedelta(days = 30)
    one_year_ago = today - datetime.timedelta(days = 365)
    # revenue from last month
    query = f'''SELECT sum(sold_price) as rev FROM ticket NATURAL JOIN purchases WHERE ticket.airline_name = \'{airline_name}\' and purchases.purchase_date >= \'{one_month_ago.strftime("%Y-%m-%d")}\''''
    if cursor.execute(query):
        month_rev = cursor.fetchone()['rev']

    # revenue from last year
    query = f'''SELECT sum(sold_price) as rev FROM ticket NATURAL JOIN purchases WHERE ticket.airline_name = \'{airline_name}\' AND purchases.purchase_date >= \'{one_year_ago.strftime("%Y-%m-%d")}\''''
    if cursor.execute(query):
        year_rev = cursor.fetchone()['rev']

    if not month_rev:
        month_rev = 0
    if not year_rev:
        year_rev = 0

    cursor.close()
    return render_template("revenue.html", month_rev=month_rev, year_rev=year_rev)


@app.route("/customerPurchase", methods=["POST", "GET"])
@require_cust_login
def customerPurchase():
    cursor = conn.cursor()
    error = None
    cust_email = session['Username']

    airline_name = request.form['airline_name']
    flight_number = request.form['flight_num']
    departure_date = request.form['departure_date']
    departure_time = request.form['departure_time']

    card_type = request.form['card_type']
    card_number = request.form['card_number']
    card_name = request.form['card_name']
    exp_date = request.form['card_expiration_date']

    today = datetime.today().strftime('%Y-%m-%d')
    if exp_date <= today:
        error= "Card has expired. Try a valid card"
        cursor.close()
        return render_template("customer.html", error=error)

    query = "SELECT num_of_seats FROM flight natural join airplane where airline_name = \"" + airline_name + \
            "\" and flight_number = \"" + flight_number + "\" and departure_date = \"" + departure_date + \
            "\" and departure_time = \"" + departure_time + "\""
    cursor.execute(query)
    flight_capacity = cursor.fetchone()["num_of_seats"]

    query = "SELECT COUNT(ticket_id) AS num_tickets FROM ticket"
    cursor.execute(query)
    num_tickets = cursor.fetchone()['num_tickets']

    query = "SELECT COUNT(ticket_id) as num_seats_bought FROM ticket natural join flight natural joing purchase where airline_name = \"" \
            + airline_name + "\" and flight_number = \"" + flight_number + "\" and departure_date = \"" + departure_date \
            + "\" and departure_time = \"" + departure_time + "\" and customer_email IS NOT NULL"
    cursor.execute(query)
    num_seats_bought = cursor.fetchone()['num_seats_bought']

    query = "SELECT base_price FROM flight natural join airplane where airline_name = \"" + airline_name +\
            "\" and flight_number = \"" + flight_number + "\" and departure_date = \"" + departure_date + \
            "\" and departure_time = \"" + departure_time + "\""
    cursor.execute(query)
    base_price = cursor.fetchone()['base_price']

    if num_seats_bought >= flight_number * 0.6 and num_seats_bought < flight_capacity:
        price_of_ticket = base_price * 1.25
    elif num_seats_bought < flight_number * 0.6 and num_seats_bought < flight_capacity:
        price_of_ticket = base_price
    else:
        error = "Flight is full, choose another flight"
        cursor.close()
        return render_template("customer.html", error=error)

    # flight has seats open, need to make new ticket

    ticket_id = num_tickets + 1
    query = "INSERT INTO ticket VALUES(\""+ ticket_id +"\", \""+ airline_name +"\", \""+ flight_number +"\")"
    if not cursor.execute(query):
        error="Error occured. Please attempt purchase again"
        cursor.close()
        return render_template("customer.html", error=error)
    conn.commit()

    currTime = datetime.datetime.now()
    date = currTime.strftime("\'%Y-%m-%d\'")
    time = currTime.strftime("\'%H:%M:00\'")

    query = "INSERT INTO purchase VALUES(\""+ cust_email +"\", \""+ airline_name +"\", \""+ price_of_ticket +"\", \""+ \
            date +"\", \""+ time +"\", \""+ card_type +"\", \""+ card_number +"\", \""+ card_name \
            +"\", \""+ exp_date +"\")"
    if not cursor.execute(query):
        error="Purchase unsuccessful. Try again."
        cursor.close()
        return render_template("customer.html", error=error)
    conn.commit()
    cursor.close()

    return render_template("customer.html", error="Purchase successful!")


@app.route('/logout', methods=["GET"])
def logout():
    session.pop('Username')
    if session["userType"] == "staff":
        session.pop("airline_name")
    session.pop("userType")
    return render_template("index.html", error="Successfully logged out")


if __name__ == "__main__":
    app.run('127.0.0.1', 5000, debug=True)