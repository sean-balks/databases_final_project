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


@app.route("/rate", methods=["GET", "POST"])
@require_cust_login
def rateFlight():
    cursor = conn.cursor()
    error = ""
    query = f'''SELECT * FROM Purchases NATURAL JOIN Ticket NATURAL JOIN Flight WHERE customer_email = \'{session['Username']}\' AND arrival_date < CURRENT_DATE()'''
    cursor.execute(query)
    results = cursor.fetchall()
    if request.method == "POST":
        form = request.form.to_dict()
        custComment = form['comment']
        custRating = form['rating']
        flightNum = list(form)[2]
        customerEmail = session['Username']


        # We decided to only allow for a customer to rate a flight if they have not done so already
        query = f'''select customer_email, flight_number from Rates where customer_email = \'{customerEmail}\' and flight_number = {flightNum}'''
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


@app.route("/spending", methods=["POST", "GET"])
@require_cust_login
def customerSpending():
    today = datetime.datetime.now()
    # default shows spendings from the past year
    oneYearAgo = today - datetime.timedelta(days = 365)
    date2 = today.strftime("%Y-%m-%d")
    date1 = oneYearAgo.strftime("%Y-%m-%d")


    cursor = conn.cursor()
    query = f'''SELECT sold_price from Purchases where customer_email = \'{session['Username']}\' and purchase_date > \'{date1}\''''
    cursor.execute(query)

    totalSpent = 0
    for price in cursor.fetchall():
        totalSpent += price['sold_price']

    months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']

    # getting purchase records by each month for the past 6 months
    monthlyExpend = []
    currMonth = int(today.strftime("%m"))
    currYr = int(today.strftime("%Y"))
    if currMonth >= 6:  # we can easily get the previous 6 months
        bar_labels = months[currMonth - 6 : currMonth]
        for mon in range(1, currMonth + 1):
            query = f'''SELECT sold_price from Purchases where customer_email = \'{session['Username']}\' and month(purchase_date) = {mon} and year(purchase_date) = {currYr}'''
            cursor.execute(query)
            monthlySpending = 0
            # calculate the amount spent for the current month
            for price in cursor.fetchall():
                monthlySpending += price['sold_price']
            monthlyExpend.append(monthlySpending)
    else: # have to deal with wrapping months before january
        extraMonths = months[12 - (6 - currMonth):] # get end of last year
        bar_labels = extraMonths + months[:currMonth]
        extra = 6 - currMonth
        for mon in range((13 - extra), 13): # last year's months
            query = f'''select sold_price from purchases where customer_email = \'{session['Username']}\' and month(purchase_date) = {mon} and year(purchase_date) = {currYr - 1}'''
            cursor.execute(query)
            monthlySpending = 0
            for price in cursor.fetchall():
                monthlySpending += price['sold_price']
            monthlyExpend.append(monthlySpending)
        for mon in range(1, currMonth + 1): # this year's months
            query = f'''select sold_price from purchases where customer_email = \'{session['Username']}\' and month(purchase_date) = {mon} and year(purchase_date) = {currYr}'''
            cursor.execute(query)
            monthlySpending = 0
            for price in cursor.fetchall():
                monthlySpending += price['sold_price']
            monthlyExpend.append(monthlySpending)

    # The user requested specific months to show
    if request.method == "POST":  # recalculate total spent for the specified range
        monthlyExpend = []
        date1 = request.form['date1']
        date2 = request.form['date2']
        datetime1 = datetime.datetime.strptime(date1, "%Y-%m-%d")
        datetime2 = datetime.datetime.strptime(date2, "%Y-%m-%d")


        months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
        query = f''' SELECT sold_price from Purchases where customer_email = \'{session['Username']}\' and purchase_date > \'{date1}\' and purchase_date < \'{date2}\''''
        cursor.execute(query)
        totalSpent = 0
        for price in cursor.fetchall():
            totalSpent += price['sold_price']
        # Get monthly spendings for specified range of dates
        monthDiff = 0
        if datetime1.year == datetime2.year:
            bar_labels = months[datetime1.month - 1:datetime2.month]
            monthDiff = datetime2.month - datetime1.month
        else:  #range spans over multiple years
            monthDiff = (12 - datetime1.month) + datetime2.month
            beginningMonths = months[datetime1.month - 1:]
            endMonths = months[:datetime2.month]
            yearDiff = (int(datetime2.strftime("%Y")) - int(datetime1.strftime("%Y")))
            for mon in range(1, yearDiff):
                monthDiff += 12
                beginningMonths += months
            bar_labels = beginningMonths + endMonths



        loop_date = datetime2
        for mon in range(monthDiff + 1):
            monthNum = loop_date.strftime("%m")
            yearNum = loop_date.strftime("%Y")
            query = f'''SELECT sold_price from Purchases where customer_email = \'{session['Username']}\' AND month(purchase_date) = {monthNum} AND year(purchase_date) = {yearNum} AND purchase_date <= \'{datetime2.strftime("%Y-%m-%d")}\' and purchase_date >= \'{datetime1.strftime("%Y-%m-%d")}\''''
            cursor.execute(query)
            monthlySpending = 0
            for item in cursor.fetchall():
                monthlySpending += item.get("sold_price")
            monthlyExpend.insert(0, monthlySpending)
            loop_date = changeInMonths(loop_date, -1)  #account for wrapping months
    cursor.close()
    return render_template("customer.html", total=totalSpent, max = 25000, labels=bar_labels, values=monthlyExpend, old=date1, today=date2)



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


@app.route("/ratings", methods=["POST", "GET"])
@require_staff_login
def ratings():
    cursor = conn.cursor()
    query = "SELECT * from Flight where airline_name = \"" + session["airline_name"] + "\""
    cursor.execute(query)
    results = cursor.fetchall()
    if request.method == "POST":
        flight_num = request.form["flight_num"]
        query = "SELECT AVG(`rating`) FROM `Rates` WHERE flight_number =" + flight_num
        cursor.execute(query)
        avgRating = cursor.fetchone()["AVG(`rating`)"]
        if not avgRating:
            avgRating = 0
        query = "SELECT customer_email, comment, rating FROM `Rates` WHERE flight_number =" + flight_num
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        return render_template("staff.html", average=avgRating, results=results)
    cursor.close()
    return render_template("staff.html", results=results)


@app.route("/reports", methods=["POST", "GET"])
@require_staff_login
def reports():
    values = []
    chartTitle = "Number of Tickets Sold"
    total = 0
    months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
    cursor = conn.cursor()
    if request.method == "POST": #user entered a specific range of dates
        values = []
        beg_date = request.form['beg_date']
        end_date = request.form['end_date']
        datetime1 = datetime.datetime.strptime(beg_date, "%Y-%m-%d")
        datetime2 = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        month_diff = 0
        if datetime1.year == datetime2.year:
            bar_labels = months[datetime1.month - 1:datetime2.month]
            month_diff = datetime2.month - datetime1.month
        else:
            month_diff = (12 - datetime1.month) + datetime2.month
            labels1 = months[datetime1.month - 1:]
            labels2 = months[:datetime2.month]
            year_diff = (int(datetime2.strftime("%Y")) - int(datetime1.strftime("%Y")))
            for ind in range(1, year_diff):
                month_diff += 12
                labels1 += months
            bar_labels = labels1 + labels2
        loop_date = datetime2
        for ind in range(month_diff + 1):
            month_num = loop_date.strftime("%m")
            year_num = loop_date.strftime("%Y")
            loop_date = changeInMonths(loop_date, -1)
            query = f'''SELECT count(ticket_id) FROM Ticket NATURAL JOIN Purchases WHERE Ticket.airline_name = \'{session['airline_name']}\' 
            and extract(month from Purchases.purchase_date) = {month_num} 
            AND extract(year from  Purchases.purchase_date) = {year_num}
            and purchase_date <= \'{datetime2}\' and purchase_date >= \'{datetime1}\''''
            cursor.execute(query)
            num_tickets_sold = cursor.fetchone()['count(ticket_id)']
            values.insert(0, num_tickets_sold)
        total = sum(values)
    cursor.close()
    return render_template("staff.html", old=beg_date, today=end_date, total=total, values=values, title=chartTitle, labels=bar_labels, max=100)


@app.route("/revenue")
@require_staff_login
def revenue():
    graph_title = "View Yearly and Monthly Revenue"
    month_values = []
    year_values = []

    airline_name = session['airline_name']
    cursor = conn.cursor()

    today = datetime.datetime.now()
    one_month_ago = today - datetime.timedelta(days = 30)
    one_year_ago = today - datetime.timedelta(days = 365)
    # revenue from last month
    query = f'''SELECT sum(sold_price) FROM Ticket NATURAL JOIN Purchases WHERE Ticket.airline_name = \'{airline_name}\' and Purchases.purchase_date >= \'{one_month_ago.strftime("%Y-%m-%d")}\''''
    cursor.execute(query)
    month_rev = cursor.fetchone()['sum(sold_price)']
    if month_rev:
        month_values.append(int(month_rev))
    else:
        month_values.append(0)

    # revenue from last year
    query = f'''SELECT sum(sold_price) FROM Ticket NATURAL JOIN Purchases WHERE Ticket.airline_name = \'{airline_name}\' AND Purchases.purchase_date >= \'{one_year_ago.strftime("%Y-%m-%d")}\''''
    cursor.execute(query)
    year_rev = cursor.fetchone()['sum(sold_price)']
    if (year_rev):
        year_values.append(int(year_rev))
    else:
        year_values.append(0)
    cursor.close()
    return render_template("staff.html", title=graph_title, max=25000, m_val = month_values, y_val = year_values)


@app.route("/customerPurchase/<flight_info>", methods=["POST", "GET"])
@require_cust_login
def customerPurchase(flight_info):
    cursor = conn.cursor()
    error = None
    results = flight_info.split("|")
    flight_num = results[0]

    airline_name = results[1]
    base_price = results[2]
    depDate = results[3]
    depTime = results[4]

    query = f'''select airplane_id from Flight where flight_number = {flight_num} and departure_date = \'{depDate}\' and departure_time = \'{depTime}\''''
    cursor.execute(query)
    airplane_id = cursor.fetchone()['airplane_id']
    query = f'''select num_seats from Airplane where airplane_id = {airplane_id}'''
    cursor.execute(query)

    num_seats = cursor.fetchone()['num_seats']

    query = f'''select count(*) from Ticket where flight_number = {flight_num}'''
    cursor.execute(query)
    number_of_pass = cursor.fetchone()['count(*)']
    if number_of_pass >= (num_seats * 0.7):
        base_price *= 1.2

    currTime = datetime.datetime.now()
    date = currTime.strftime("\'%Y-%m-%d\'")
    time = currTime.strftime("\'%H:%M:00\'")

    query = f'''SELECT ticket_id FROM Ticket ORDER BY ticket_id DESC LIMIT 1'''
    cursor.execute(query)
    ticket_id = cursor.fetchone()['ticket_id'] # get the last ticket_id, add 1
    ticket_id += 1
    if ticket_id > 99999999: # all possible ticket_id already used, need to wrap back to 0
        ticket_id = 0
    if request.method == "POST":
        query = f'''insert into Purchases values ({ticket_id}, \'{session['Username']}\', null, {base_price}, {date}, {time}, \'{request.form['cardType']}\', {request.form['cardNumber']}, \'{request.form['cardName']}\', \'{request.form['expDate']}\')'''
        cursor.execute(query)
        query = f'''insert into ticket values ({ticket_id}, \'{airline_name}\', {flight_num})'''
        cursor.execute(query)
        error = "Succesful Purchase!"
    cursor.close()
    return render_template("customer.html", name=airline_name, number=flight_num, price=base_price, error=error, date=depDate, time=depTime)


@app.route('/logout', methods=["GET"])
def logout():
    session.pop('Username')
    return render_template("index.html", error="Successfully logged out")


if __name__ == "__main__":
    app.run('127.0.0.1', 5000, debug=True)