from flask import Flask, render_template, request, session, url_for, redirect
#import pymysql

app = Flask(__name__)

@app.route('/')
def hello():
    return render_template('index.html')

"""
@app.route('/login')
def login():
    return render_template('login.html')
"""



if __name__ == "__main__":
    app.run('127.0.0.1', 5000, debug=True)