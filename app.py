#!/usr/bin/env python
from flask import Flask, render_template, flash, redirect, url_for, session, request, logging
from flask_mysqldb import MySQL
from wtforms import Form, StringField, validators, SelectField, PasswordField
from passlib.hash import sha256_crypt
from functools import wraps
import os
import sys
from time import sleep
import uuid

from rq import Worker, Queue, Connection

from worker import conn
from scrape import scrape
from send_mail import send_mail, notify_admin, send_mail_attachment

import json
from googleplaces import GooglePlaces, types, lang
import csv

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

# T&Cs
@app.route('/terms')
def terms():
    return render_template('terms.html')

# Imprint
@app.route('/imprint')
def imprint():
    return render_template('imprint.html')

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

        print(session['username'], 'created a new user with username:', username)

        # Close connection
        cur.close()

        flash('You are now registered and can log in', 'success')

        return redirect(url_for('index'))
    return render_template('register.html', form=form)

# LeadForm
class LeadForm(Form):
    queries = StringField('', [validators.Length(min=2, max=100), validators.required()], render_kw={"placeholder": "Bar, Cafe, Gym..."})
    locations = StringField('', [validators.Length(min=2, max=100), validators.required()], render_kw={"placeholder": "London, New York..."})
    place_type = SelectField('', choices=[('choose', 'Choose...'),
                                            ('bakery', 'Bakery'),
                                            ('bar', 'Bar'),
                                            ('beauty_salon', 'Beauty salon'),
                                            ('bicycle_store', 'Bicycle store'),
                                            ('book_store', 'Book store'),
                                            ('bowling_alley', 'Bowling alley'),
                                            ('cafe', 'Cafe'),
                                            ('campground', 'Campground'),
                                            ('car_dealer', 'Car dealer'),
                                            ('car_rental', 'Car rental'),
                                            ('car_repair', 'Car repair'),
                                            ('car_wash', 'Car wash'),
                                            ('clothing_store', 'Clothing store'),
                                            ('dentist', 'Dentist'),
                                            ('department_store', 'Department store'),
                                            ('doctor', 'Doctor'),
                                            ('electrician', 'Electrician'),
                                            ('electronics_store', 'Electronics store'),
                                            ('florist', 'Florist'),
                                            ('furniture_store', 'Furniture store'),
                                            ('gym', 'Gym'),
                                            ('hair_care', 'Hair care'),
                                            ('hardware_store', 'Hardware store'),
                                            ('insurance_agency', 'Insurance agency'),
                                            ('jewelry_store', 'Jewelry store'),
                                            ('laundry', 'Laundry'),
                                            ('lawyer', 'Lawyer'),
                                            ('locksmith', 'Locksmith'),
                                            ('lodging', 'Lodging'),
                                            ('meal_delivery', 'Meal delivery'),
                                            ('meal_takeaway', 'Meal takeaway'),
                                            ('movie_theater', 'Movie theater'),
                                            ('moving_company', 'Moving company'),
                                            ('museum', 'Museum'),
                                            ('night_club', 'Night club'),
                                            ('painter', 'Painter'),
                                            ('pet_store', 'Pet store'),
                                            ('pharmacy', 'Pharmacy'),
                                            ('physiotherapist', 'Physiotherapist'),
                                            ('plumber', 'Plumber'),
                                            ('real_estate_agency', 'Real estate agency'),
                                            ('restaurant', 'Restaurant'),
                                            ('roofing_contractor', 'Roofing contractor'),
                                            ('school', 'School'),
                                            ('shoe_store', 'Shoe store'),
                                            ('shopping_mall', 'Shopping mall'),
                                            ('spa', 'Spa'),
                                            ('travel_agency', 'Travel agency'),
                                            ('veterinary_care', 'Veterinarian'),
                                            ('zoo', 'Zoo')])

    filters_include = StringField('', [validators.Length(max=100)])
    filters_exclude = StringField('', [validators.Length(max=100)])
    email = StringField('', [validators.Length(max=40)], render_kw={"placeholder": "Email"})

# Dashboard
@app.route('/dashboard', methods=['GET', 'POST'])
@is_logged_in
def dashboard():
    # Create cursor
    cur = mysql.connection.cursor()
    eval = cur.execute("SELECT evaluation_state FROM users WHERE username = %s", [session['username']])

    #if eval == 1:
        #return redirect(url_for('thanks'))

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
            place_type = form.place_type.data
            max_leads = request.form.get('max_leads') # check if that works

            print(session['username'], ' started a preview for ', query, ' in ', city)
            # prepare data

            data = []
            place_ids = []
            names = []
            count = 0

            google_places = GooglePlaces(os.environ['GP_API_KEY1'])

            query_list = query.split(',')
            city_list = city.split(',')
            filters_exclude_list = filters_exclude.replace(' ', '').split(',')
            filters_include_list = filters_include.replace(' ', '').split(',')

            for city in city_list:
                if count > 20:
                    break
                for query in query_list:
                    if count > 20:
                        break
                    try:
                        if place_type != 'choose':
                            query_result = google_places.nearby_search(keyword=query, radius=int(os.environ['SEARCH_RADIUS']), location=city, types=[place_type])
                        else:
                            query_result = google_places.nearby_search(keyword=query, radius=int(os.environ['SEARCH_RADIUS']), location=city)

                        for place in query_result.places:
                            place.get_details()

                            if filters_exclude != '':
                                if any(word.strip().lower() in place.name.lower() for word in filters_exclude_list):
                                    continue

                            if filters_include != '':
                                if any(word.strip().lower() in place.name.lower() for word in filters_include_list):
                                    pass
                                else:
                                    continue

                            if place.website != None and place.name not in names and city.strip().lower() in place.formatted_address.lower():
                                count += 1
                                print('preview lead count:', count)
                                if count > 20:
                                    break
                                names.append(place.name)
                                data.append([str(count), place.name, "********", place.formatted_address, "********", "********"])

                    except Exception as e:
                        print(e)
                        flash('An unknown error occured. Please try again in a minute. If the error keeps coming contact an admin.', 'danger')
                        return render_template('dashboard.html', form=form)


            return render_template('dashboard.html', data=data, form=form)


    if request.method == 'POST' and 'submit' in request.form:

        if form.validate() != True:
            flash('Something went wrong. Please check everything and submit again.', 'danger')
            return render_template('dashboard.html', form=form)
        elif 'checkbox' not in request.form:
            flash('Please confirm that you did a preview and enter a valid email address.', 'danger')
            return render_template('dashboard.html', form=form)
        else:
            query = form.queries.data
            city = form.locations.data
            email = form.email.data
            filters_exclude = form.filters_exclude.data
            filters_include = form.filters_include.data
            place_type = form.place_type.data
            max_leads = request.form.get('max_leads')
            user = session['username']
            uid = uuid.uuid1()

            q = Queue(connection=conn)

            # catch lat lng error - whats about that? - occurs in scrape.py - messy fix so far

            q.enqueue(notify_admin, query, city, email, filters_include, filters_exclude, place_type, user, max_leads)
            q.enqueue(scrape, args=(query, city, place_type, filters_exclude, filters_include, max_leads, user, uid), timeout=54000)
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
    app.run(host='0.0.0.0', port=port,debug=os.environ['APP_DEBUG'])
