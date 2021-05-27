""" Copyright (c) 2021 Cisco and/or its affiliates.
This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at
           https://developer.cisco.com/docs/licenses
All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.
"""

# Import Section
from flask import Flask, render_template, request, redirect
import json
import os
import requests
import datetime
import time
from webexteamssdk import WebexTeamsAPI
from itertools import islice
from dotenv import load_dotenv

# load all environment variables
load_dotenv()

AUTHORIZATION_BASE_URL = 'https://api.ciscospark.com/v1/authorize'
TOKEN_URL = 'https://api.ciscospark.com/v1/access_token'
SCOPE = 'spark:all'

#initialize variabes for URLs
#REDIRECT_URL must match what is in the integration, but we will construct it below in __main__
# so no need to hard code it here
PUBLIC_URL='http://0.0.0.0:5000'
REDIRECT_URI=""

app = Flask(__name__)
ACCESS_TOKEN=os.getenv("WEBEX_TEAMS_ACCESS_TOKEN")

#Methods
#Returns location and time of accessing device
def getSystemTimeAndLocation():
    #request user ip
    userIPRequest = requests.get('https://get.geojs.io/v1/ip.json')
    userIP = userIPRequest.json()['ip']

    #request geo information based on ip
    geoRequestURL = 'https://get.geojs.io/v1/ip/geo/' + userIP + '.json'
    geoRequest = requests.get(geoRequestURL)
    geoData = geoRequest.json()

    #create info string
    location = geoData['country']
    timezone = geoData['timezone']
    current_time=datetime.datetime.now().strftime("%d %b %Y, %I:%M %p")
    timeAndLocation = "System Information: {}, {} (Timezone: {})".format(location, current_time, timezone)

    return timeAndLocation

##Routes
@app.route('/')
def login():
    return render_template('login.html')

@app.route('/admin')
def admin():
    with open("./guests.json", "r") as data:
        guests = json.loads(data.read()) # Alvin: Update this if you are not using JSON file for storage, and also update the schema
        return render_template('admin.html', guests=guests, logged_in=True, timeAndLocation=getSystemTimeAndLocation())

@app.route('/guest', methods=["POST"])
def guest():

    #username = request.form['username']
    #password = request.form['password']
    #print(username)
    #print(password)
    username=request.form.get('username')
    password=request.form.get('password')
    print('Username: ',username)
    print('Password: ',password)

    with open("./guests.json", "r") as data:
        guests = json.loads(data.read()) # Alvin: Update this if you are not using JSON file for storage, and also update the schema
    data.close()

    was_found = False
    for index, guest in enumerate(guests):
        if guest['username'] == username:
            was_found = True
            break
    if was_found and guests[index]['password']==password:
        api= WebexTeamsAPI(access_token=ACCESS_TOKEN)
        subject = guests[index]['username']
        display_name = guests[index]['name']
        guest_issuer_id = os.getenv("GUEST_ISSUER_ID")
        expiration_time = os.getenv("GUEST_TOKEN_EXPIRATION")
        secret = os.getenv("GUEST_SHARED_SECRET")
        guestT = api.guest_issuer.create(subject, display_name, guest_issuer_id, str(int(time.time())+int(expiration_time)), secret)
        print("Obtained guest token for login: ",guestT.token)
        webexapi = WebexTeamsAPI(access_token=guestT.token)
        rooms = webexapi.rooms.list(sortBy="lastactivity")
        room_list = list(islice(rooms, 30)) # Alvin: You may remove this line as there are too many rooms to be returned, leading to long loading time for testing



        # Alvin: You would pass the guest token as guest_token below
        #TODO: Alvin to avoid passing to guest.html all passwords !!!
        return render_template('guest.html', guests=guests, rooms=room_list, guest_token=guestT.token, logged_in=True, timeAndLocation=getSystemTimeAndLocation())
    else:
        if was_found:
            print("Invalid password for guest.")
        else:
            print("Guest Username not found.")
        #TODO: Alvin show user that they had the wrong username or password when rendering login.html from here.
        return render_template('login.html')

@app.route('/create_guest', methods=["POST"])
def create_guest():
    name = request.form['new-name']
    username = request.form['new-username']
    password = request.form['new-password']
    allowed_conn = request.form['new-allowed-conn'].split(",")
    print(name)
    print(username)
    print(password)
    print(allowed_conn)
    # Alvin: Logic of Adding Guest
    api = WebexTeamsAPI(access_token=ACCESS_TOKEN)
    #api = WebexTeamsAPI()
    subject = username
    display_name = name
    guest_issuer_id = os.getenv("GUEST_ISSUER_ID") # The guest issuer id. You can obtain this from developer.webex.com
    expiration_time = os.getenv("GUEST_TOKEN_EXPIRATION") # Unix timestamp of how long this guest issuer should be valid for.
    secret = os.getenv("GUEST_SHARED_SECRET") # The secret, also obtained from developer.webex.com

    guest = api.guest_issuer.create(subject, display_name, guest_issuer_id, str(int(time.time())+int(expiration_time)), secret)
    print('Guest Token: ',guest.token)
    api2 = WebexTeamsAPI(access_token=guest.token)
    mePerson=api2.people.me()
    print("PersonID: ",mePerson.id)
    personid=mePerson.id

    with open("./guests.json", "r") as data:
        guests = json.loads(data.read()) # Alvin: Update this if you are not using JSON file for storage, and also update the schema
    data.close()

    new_guest={"id": personid, "name": name, "username": username, "password": password, "allowed_conn": allowed_conn}
    guests.append(new_guest)

    with open("./guests.json", "w") as filehandle:
        json.dump(guests, filehandle)
    filehandle.close()

    return redirect("/admin")


@app.route('/edit_guest', methods=["POST"])
def edit_guest():
    id = request.form['id']
    name = request.form['name']
    username = request.form['username']
    password = request.form['password']
    allowed_conn = json.loads(request.form['allowed_conn'])
    # Alvin: Logic of Guest Record Update
    #TODO: Alvin to dissallow editing of anything but the password and allowed_conn or it will break the Guest token mechanism
    with open("./guests.json", "r") as data:
        guests = json.loads(data.read()) # Alvin: Update this if you are not using JSON file for storage, and also update the schema
    data.close()

    was_found=False

    for index,guest in enumerate(guests):
        if guest['id']==id:
            was_found=True
            break

    if was_found:
        changed_guest=guests[index]
        changed_guest['password']=password
        changed_guest['allowed_conn'] = allowed_conn
        del guests[index]
        guests.append(changed_guest)
        with open("./guests.json", "w") as filehandle:
            json.dump(guests, filehandle)
        filehandle.close()
    return "200"

@app.route('/delete_guest', methods=["POST"])
def delete_guest():
    id = request.form['id']
    # Alvin: Logic of Guest Record Removal
    print("id to remove:", id)
    with open("./guests.json", "r") as data:
        guests = json.loads(
            data.read())  # Alvin: Update this if you are not using JSON file for storage, and also update the schema
    data.close()

    was_found = False

    for index, guest in enumerate(guests):
        if guest['id'] == id:
            print("was found!")
            was_found = True
            break

    if was_found:
        del guests[index]
        with open("./guests.json", "w") as filehandle:
            json.dump(guests, filehandle)
        filehandle.close()
    return "200"

@app.route('/connect_guest', methods=["POST"])
def connect_guest():
    ids = request.form['connect_ids'].split(",")
    print("IDs received: ",ids)
    # Alvin: Response to "Connect" button
    if len(ids)>1:
        api = WebexTeamsAPI(access_token=ACCESS_TOKEN)
        roomname="guestconn"
        for the_id in ids:
            roomname=roomname+the_id[-4:]
        the_room=api.rooms.create(roomname)
        print("Created room ID: ",the_room.id)
        for the_id in ids:
            the_membership=api.memberships.create(the_room.id,the_id)
            print("Created a membership: ",the_membership.id)
    else:
        print("Need at least 2 ids to connect in a space.")
    return "200"

#Main Function
if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=False)

