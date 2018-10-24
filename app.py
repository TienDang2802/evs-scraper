#!/usr/bin/env python
from flask import Flask, render_template, flash, redirect, url_for, session, request, logging
from flask_mysqldb import MySQL
from wtforms import Form, StringField, validators, SelectField, PasswordField
from passlib.hash import sha256_crypt
from functools import wraps
import uuid

from rq import Worker, Queue, Connection

from worker import conn
from scrape import scrape
from send_mail import notify_admin, send_mail_attachment
from scrape import process_filter
from googleplaces import GooglePlaces, types, lang

import os

app = Flask(__name__)

# Config MySQL
app.config['MYSQL_HOST'] = os.environ['MYSQL_HOST']
app.config['MYSQL_USER'] = os.environ['MYSQL_USER']
app.config['MYSQL_PASSWORD'] = os.environ['MYSQL_PASSWORD']
app.config['MYSQL_DB'] = os.environ['MYSQL_DB']
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
# init MYSQL
mysql = MySQL(app)

# Index
@app.route('/', methods=['GET', 'POST'])
def index():
    if 'logged_in' in session:
        print(session['username'], 'logged in')
        return redirect(url_for('dashboard'))
    else:
        if request.method == 'POST':
            # Get Form Fields
            username = request.form['username']
            password_candidate = request.form['password']

            # Create cursor
            cur = mysql.connection.cursor()

            # Get user by username
            result = cur.execute("SELECT * FROM users WHERE username = %s", [username])

            if result > 0:
                # Get stored hash
                data = cur.fetchone()
                password = data['password']

                # Compare Passwords
                if sha256_crypt.verify(password_candidate, password):
                    # Passed
                    session['logged_in'] = True
                    session['username'] = username
                    
                    print(session['username'], 'logged in')
                    flash('You are now logged in', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    error = 'Invalid login'
                    return render_template('home.html', error=error)
                # Close connection
                cur.close()
            else:
                error = 'Username not found'
                return render_template('home.html', error=error)

        return render_template('home.html')

# Check if user logged in
def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('Unauthorized, Please login', 'danger')
            return redirect(url_for('index'))
    return wrap

# Logout
@app.route('/logout')
@is_logged_in
def logout():
    session.clear()
    flash('You are now logged out', 'success')
    return redirect(url_for('index'))
    
# Register Form Class
class RegisterForm(Form):
    name = StringField('Name', [validators.Length(min=1, max=50)])
    username = StringField('Username', [validators.Length(min=4, max=25)])
    email = StringField('Email', [validators.Length(min=6, max=50)])
    password = PasswordField('Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords do not match')
    ])
    confirm = PasswordField('Confirm Password')


# User Register
@app.route('/register', methods=['GET', 'POST'])
@is_logged_in
def register():
    form = RegisterForm(request.form)
    if request.method == 'POST' and form.validate():
        name = form.name.data
        email = form.email.data
        username = form.username.data
        password = sha256_crypt.encrypt(str(form.password.data))

        # Create cursor
        cur = mysql.connection.cursor()

        # Execute query
        cur.execute("INSERT INTO users(name, email, username, password) VALUES(%s, %s, %s, %s)", (name, email, username, password))

        # Commit to DB
        mysql.connection.commit()
        
        #print(session['username'], 'created a new user with username:', username)
        
        # Close connection
        cur.close()

        flash('You are now registered and can log in', 'success')

        return redirect(url_for('index'))
    return render_template('register.html', form=form)

# LeadForm
class LeadForm(Form):
    queries = StringField('', [validators.Length(min=2, max=100), validators.required()], render_kw={"placeholder": "Rental, cottage..."})
    locations = StringField('', [validators.Length(min=2, max=100), validators.required()], render_kw={"placeholder": "Brighton, Florida..."})
    filters_include = StringField('', [validators.Length(max=100)])
    filters_exclude = StringField('', [validators.Length(max=100)])
    email = StringField('', [validators.Length(max=40)], render_kw={"placeholder": "Email"})

# Dashboard
@app.route('/dashboard', methods=['GET', 'POST'])
@is_logged_in
def dashboard():
    # Create cursor
    cur = mysql.connection.cursor()

    form = LeadForm(request.form)

    if request.method == 'POST' and 'preview' in request.form:

        if form.validate() != True:
            flash('Something went wrong. Please check everything and submit again.', 'danger')
            return render_template('dashboard.html', form=form)

        else:
            query = form.queries.data
            city = form.locations.data
            filters_exclude = form.filters_exclude.data
            filters_include = form.filters_include.data
            user = session['username']

            print(session['username'], ' started a preview for ', query, ' in ', city)

            data = process_filter(query, city, filters_exclude, filters_include, user, True)

            return render_template('dashboard.html', data=data, form=form, request_method=request.method)


    if request.method == 'POST' and 'submit' in request.form:

        if form.validate() != True:
            flash('Something went wrong. Please check everything and submit again.', 'danger')
            return render_template('dashboard.html', form=form)
        else:
            query = form.queries.data
            city = form.locations.data
            email = form.email.data
            filters_exclude = form.filters_exclude.data
            filters_include = form.filters_include.data
            max_leads = request.form.get('max_leads')
            user = session['username']
            uid = uuid.uuid1()

            q = Queue(connection=conn)

            q.enqueue(notify_admin, query, city, email, filters_include, filters_exclude, user, max_leads)
            q.enqueue(scrape, args=(query, city, filters_exclude, filters_include, user, uid), timeout=36000)
            q.enqueue(send_mail_attachment, email, user, uid)

            cur.close()
            return redirect(url_for('thanks'))

    return render_template('dashboard.html', form=form)

    # Close connection
    cur.close()

@app.route('/thanks')
@is_logged_in
def thanks():
    return render_template('thanks.html')

if __name__ == '__main__':
    app.secret_key = os.environ['APP_SECRET_KEY']
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ['APP_DEBUG'])
