from flask import Flask, render_template, request, session, url_for, redirect
import pymysql
import hashlib

app = Flask(__name__)

conn = pymysql.connect(host='localhost',
                       user='root',
                       password='',
                       db='project',
                       charset='utf8mb4',
                       port=3306,
                       cursorclass=pymysql.cursors.DictCursor)

@app.route('/')
def hello():
    return render_template('index.html')


@app.route('/login')
def login():
    error = None
    cursor = conn.cursor()
    if request.method == 'POST':
        #check if they already have credentials in the DB
        hexHashPass = hashlib.md5(request.form['Password'].encode()).hexdigest()
        customerQuery = "select * from Customer where customer_email = \"" + request.form['Username'] + "\" AND password = \"" \
                        + hexHashPass + "\""
        staffQuery = "select * from Staff where customer_email = \"" + request.form['Username'] + "\" AND password = \"" \
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


@app.route('/loginAuth', methods=['GET','POST'])
def loginAuth():
    username = request.form('Username')
    password = request.form('Password')

    cursor = conn.cursor()

    query = 'SELECT * FROM user WHERE username = %s and password = %s'
    cursor.execute(query, (username, password))

    data = cursor.fetchone()

    cursor.close()
    if(data):
        session['username'] = username

        return redirect(url_for('home'))
    else:
        error = 'Invalid login or username'
        return render_template('login.html', error=error)


@app.route("/", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        userType = request.form['text_acc_type']  # customer, agent, staff
        if userType == "customer":
            return redirect(url_for('registerCustomer'))
        elif userType == "staff":
            return redirect(url_for('registerStaff'))
    return render_template("register.html", error=error)


# NEED TODO - add a register page for users to add all of their info listed in the queries
@app.route("/registerCustomer", methods=['GET','POST'])
def registerCustomer():
    error = None
    if request.method == "POST":
        cursor = conn.cursor()
        query = "select * from Customer where customer_email = \"" + request.form['Username'] + '\"'
        if cursor.execute(query):
            error = "Account with email already exists, please use a different email"
            return render_template("index.html", error=error)
        passHash = request.form['Password']
        hashedPass = hashlib.md5(passHash.encode())
        hexHashPass = hashedPass.hexdigest()
        query = f'''INSERT INTO Customer VALUES (\'{request.form['name']}\', \'{request.form['email']}\', 
                \'{hexHashPass}\', {request.form['buildingNumber']}, \'{request.form['street']}\', 
                \'{request.form['city']}\', \'{request.form['state']}\', {request.form['phoneNumber']}, {request.form['passportNumber']},
                \'{request.form['expDate']}\', \'{request.form['passportCountry']}\', \'{request.form['dateOfBirth']}\')'''
        if cursor.execute(query):
            cursor.close()
            return redirect(url_for('login'))
    return render_template("registerCustomer.html", error=error)


# NEED TODO - add a register page for users to add all of their info listed in the queries
@app.route("/registerStaff", methods=['GET','POST'])
def registerStaff():
    error = None
    if request.method == "POST":
        cursor = conn.cursor()
        query = "select * from staff where username = \"" + request.form['Username'] + '\"'
        if cursor.execute(query):
            error = "Account with email already exists, please use a different email"
            return render_template("index.html", error=error)

        numbers = request.form["phoneNum"].split(", ")
        for num in numbers:
            query = f'''insert into StaffPhones values (\'{request.form['email']}\', {num})'''
            cursor.execute(query)

        passHash = request.form['Password']
        hashedPass = hashlib.md5(passHash.encode())
        hexHashPass = hashedPass.hexdigest()
        query = f'''INSERT INTO Staff VALUES (\'{request.form['name']}\', \'{request.form['email']}\', 
                \'{hexHashPass}\', {request.form['buildingNumber']}, \'{request.form['street']}\', 
                \'{request.form['city']}\', \'{request.form['state']}\', {request.form['phoneNumber']}, {request.form['passportNumber']},
                \'{request.form['expDate']}\', \'{request.form['passportCountry']}\', \'{request.form['dateOfBirth']}\')'''
        if cursor.execute(query):
            cursor.close()
            return redirect(url_for('login'))
    return render_template("registerStaff.html", error=error)



@app.route('/logout')
def logout():
    session.pop('username')
    return redirect('/')


if __name__ == "__main__":
    app.run('127.0.0.1', 5000, debug=True)