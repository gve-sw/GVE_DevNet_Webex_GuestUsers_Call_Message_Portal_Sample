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
from flask import Flask, render_template, request, session, redirect, url_for, jsonify, make_response
from requests_oauthlib import OAuth2Session
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
PUBLIC_URL='http://localhost:5000'
#REDIRECT_URI will be set in admin() if it needs to trigger the oAuth flow
REDIRECT_URI=""


os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

app = Flask(__name__)
#ACCESS_TOKEN=os.getenv("WEBEX_TEAMS_ACCESS_TOKEN")

app.secret_key = '123456789012345678901234'

AppAdminID=''

largespaces=[]
with open("./largespaces.json", "r") as data:
    largespaces = json.loads(data.read())

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

@app.route("/callback", methods=["GET"])
def callback():
    """
    Retrieving an access token.
    The user has been redirected back from the provider to your registered
    callback URL. With this redirection comes an authorization code included
    in the redirect URL. We will use that to obtain an access token.
    """
    global REDIRECT_URI

    print("Came back to the redirect URI, trying to fetch token....")
    print("redirect URI should still be: ",REDIRECT_URI)
    print("Calling OAuth2SEssion with CLIENT_ID ",os.getenv('CLIENT_ID')," state ",session['oauth_state']," and REDIRECT_URI as above...")
    auth_code = OAuth2Session(os.getenv('CLIENT_ID'), state=session['oauth_state'], redirect_uri=REDIRECT_URI)
    print("Obtained auth_code: ",auth_code)
    print("fetching token with TOKEN_URL ",TOKEN_URL," and client secret ",os.getenv('CLIENT_SECRET')," and auth response ",request.url)
    token = auth_code.fetch_token(token_url=TOKEN_URL, client_secret=os.getenv('CLIENT_SECRET'),
                                  authorization_response=request.url)

    print("Token: ",token)
    print("should have grabbed the token by now!")
    session['oauth_token'] = token
    with open('tokens.json', 'w') as json_file:
        json.dump(token, json_file)
    return redirect(url_for('.admin'))


#manual refresh of the token
@app.route('/refresh', methods=['GET'])
def webex_teams_webhook_refresh():

    r_api=None

    teams_token = session['oauth_token']

    # use the refresh token to
    # generate and store a new one
    access_token_expires_at=teams_token['expires_at']

    print("Manual refresh invoked!")
    print("Current time: ",time.time()," Token expires at: ",access_token_expires_at)
    refresh_token=teams_token['refresh_token']
    #make the calls to get new token
    extra = {
        'client_id': os.getenv('CLIENT_ID'),
        'client_secret': os.getenv('CLIENT_SECRET'),
        'refresh_token': refresh_token,
    }
    auth_code = OAuth2Session(os.getenv('CLIENT_ID'), token=teams_token)
    new_teams_token=auth_code.refresh_token(TOKEN_URL, **extra)
    print("Obtained new_teams_token: ", new_teams_token)
    #store new token

    teams_token=new_teams_token
    session['oauth_token'] = teams_token
    #store away the new token
    with open('tokens.json', 'w') as json_file:
        json.dump(teams_token, json_file)

    #test that we have a valid access token
    r_api = WebexTeamsAPI(access_token=teams_token['access_token'])

    return ("""<!DOCTYPE html>
                   <html lang="en">
                       <head>
                           <meta charset="UTF-8">
                           <title>Webex Teams Bot served via Flask</title>
                       </head>
                   <body>
                   <p>
                   <strong>The token has been refreshed!!</strong>
                   </p>
                   </body>
                   </html>
                """)



@app.route('/admin')
def admin():

    global REDIRECT_URI
    global PUBLIC_URL
    global ACCESS_TOKEN

    if os.path.exists('tokens.json'):
        with open('tokens.json') as f:
            tokens = json.load(f)
    else:
        tokens = None

    if tokens == None or time.time()>(tokens['expires_at']+(tokens['refresh_token_expires_in']-tokens['expires_in'])):
        # We could not read the token from file or it is so old that even the refresh token is invalid, so we have to
        # trigger a full oAuth flow with user intervention
        REDIRECT_URI = PUBLIC_URL + '/callback'  # Copy your active  URI + /callback
        print("Using PUBLIC_URL: ",PUBLIC_URL)
        print("Using redirect URI: ",REDIRECT_URI)
        teams = OAuth2Session(os.getenv('CLIENT_ID'), scope=SCOPE, redirect_uri=REDIRECT_URI)
        authorization_url, state = teams.authorization_url(AUTHORIZATION_BASE_URL)

        # State is used to prevent CSRF, keep this for later.
        print("Storing state: ",state)
        session['oauth_state'] = state
        print("root route is re-directing to ",authorization_url," and had sent redirect uri: ",REDIRECT_URI)
        return redirect(authorization_url)
    else:
        # We read a token from file that is at least younger than the expiration of the refresh token, so let's
        # check and see if it is still current or needs refreshing without user intervention
        print("Existing token on file, checking if expired....")
        access_token_expires_at = tokens['expires_at']
        if time.time() > access_token_expires_at:
            print("expired!")
            refresh_token = tokens['refresh_token']
            # make the calls to get new token
            extra = {
                'client_id': os.getenv('CLIENT_ID'),
                'client_secret': os.getenv('CLIENT_SECRET'),
                'refresh_token': refresh_token,
            }
            auth_code = OAuth2Session(os.getenv('CLIENT_ID'), token=tokens)
            new_teams_token = auth_code.refresh_token(TOKEN_URL, **extra)
            print("Obtained new_teams_token: ", new_teams_token)
            # assign new token
            tokens = new_teams_token
            # store away the new token
            with open('tokens.json', 'w') as json_file:
                json.dump(tokens, json_file)


        session['oauth_token'] = tokens
        print("Using stored or refreshed token....")
        ACCESS_TOKEN=tokens['access_token']


        with open("./guests.json", "r") as data:
            guests = json.loads(data.read()) # Alvin: Update this if you are not using JSON file for storage, and also update the schema
            return render_template('admin.html', guests=guests, logged_in=True, timeAndLocation=getSystemTimeAndLocation())

@app.route('/guest', methods=["POST"])
def guest():

    #first check to see if the AppAdmin user is logged in on the application, if not , show an error prompting for user to
    # get help from an "Admin" to get the application started properly

    global ACCESS_TOKEN
    global AppAdminID

    if os.path.exists('tokens.json'):
        with open('tokens.json') as f:
            tokens = json.load(f)
    else:
        tokens = None

    if tokens == None or time.time()>(tokens['expires_at']+(tokens['refresh_token_expires_in']-tokens['expires_in'])):
        # We could not read the token from file or it is so old that even the refresh token is invalid, so we have to
        # give an error message for Guest Login
        print("App Admin not logged in. Please contact Administrator...")
        return render_template('login.html', error=True, errormessage="App Admin not logged in. Please contact Administrator...")
    else:
        # We read a token from file that is at least younger than the expiration of the refresh token, so let's
        # check and see if it is still current or needs refreshing without user intervention
        print("Existing token on file, checking if expired....")
        access_token_expires_at = tokens['expires_at']
        if time.time() > access_token_expires_at:
            print("expired!")
            refresh_token = tokens['refresh_token']
            # make the calls to get new token
            extra = {
                'client_id': os.getenv('CLIENT_ID'),
                'client_secret': os.getenv('CLIENT_SECRET'),
                'refresh_token': refresh_token,
            }
            auth_code = OAuth2Session(os.getenv('CLIENT_ID'), token=tokens)
            new_teams_token = auth_code.refresh_token(TOKEN_URL, **extra)
            print("Obtained new_teams_token: ", new_teams_token)
            # assign new token
            tokens = new_teams_token
            # store away the new token
            with open('tokens.json', 'w') as json_file:
                json.dump(tokens, json_file)

        session['oauth_token'] = tokens
        print("Using stored or refreshed token....")
        ACCESS_TOKEN=tokens['access_token']




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
        # start the webex SDK with the AppAdmin access token since we are going to obtain a guest access token
        # for the person that is logging in
        api= WebexTeamsAPI(access_token=ACCESS_TOKEN)

        # get the personID for AppAdmin
        theResult = api.people.me()
        AppAdminID=theResult.id
        print("AppAdmin personID: ", AppAdminID)


        #subject is the unique key that tells our Guest Issure authority which guest user to obtain the access token for
        subject = guests[index]['username']
        display_name = guests[index]['name']
        guest_issuer_id = os.getenv("GUEST_ISSUER_ID")
        expiration_time = os.getenv("GUEST_TOKEN_EXPIRATION")
        secret = os.getenv("GUEST_SHARED_SECRET")
        # guest_issuer.create() is used both to create a new guest and obtain the access token for them, as long as the subject is
        # correctly set to a unique identifier (username in this sample application) it should return/create the right one.
        guestT = api.guest_issuer.create(subject, display_name, guest_issuer_id, str(int(time.time())+int(expiration_time)), secret)
        print("Obtained guest token for login: ",guestT.token)
        webexapi = WebexTeamsAPI(access_token=guestT.token)
        rooms = webexapi.rooms.list(sortBy="lastactivity")
        room_list = list(islice(rooms, 30)) # Alvin: You may remove this line as there are too many rooms to be returned, leading to long loading time for testing


        # Popping off the password from the list by the line below so the are not passed to the page used by the guest user
        # (if so, they could inspect the page and see them)
        guests = [{k: v for k, v in guest.items() if k != "password"} for guest in guests]
        return render_template('guest.html', guests=guests, rooms=room_list, guest_token=guestT.token, logged_in=True, user=display_name, timeAndLocation=getSystemTimeAndLocation())
    else:
        if was_found:
            print("Invalid password for guest.")
            return render_template('login.html', error=True, errormessage="Invalid password for guest.")
        else:
            print("Guest Username not found.")
            return render_template('login.html', error=True, errormessage="Guest Username not found.")

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
    # to create a guest token user it is not mandatory to instantiate the API with the AppAdmin token, but it does not
    # hurt either and there has been some errors thrown by the SDK in the past that can be avoided this way
    api = WebexTeamsAPI(access_token=ACCESS_TOKEN)

    subject = username
    display_name = name
    guest_issuer_id = os.getenv("GUEST_ISSUER_ID") # The guest issuer id. You can obtain this from developer.webex.com
    expiration_time = os.getenv("GUEST_TOKEN_EXPIRATION") # Unix timestamp of how long this guest issuer should be valid for.
    secret = os.getenv("GUEST_SHARED_SECRET") # The secret, also obtained from developer.webex.com
    # guest_issuer.create() is used both to create a new guest and obtain the access token for them, as long as the subject is
    # correctly set to a unique identifier (username in this sample application) it should return/create the right one.
    guest = api.guest_issuer.create(subject, display_name, guest_issuer_id, str(int(time.time())+int(expiration_time)), secret)
    print('Guest Token: ',guest.token)

    # we now have the new guest token user's access token, but we do not yet have the PersonID we want to keep around
    # to more easily add them to spaces. To be able to obtain it, we first have to re-initialize the Webex Teams SDK with the
    # access token of the guest and then call people.me() to get that PersonID and store it in our .json local file
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
    password = request.form['password']
    allowed_conn = json.loads(request.form['allowed_conn'])

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
    # First, extract the list of personIds of the guest token users we want to put together into a space
    # if you do not want to have more than one space with the same exact participants even if the space name is diffent
    # (i.e. only one "direct" 1-1 space) ,then you should check that here before proceeding.
    ids = request.form['connect_ids'].split(",")
    print("IDs received: ",ids)

    # First check to make sure they selected more than just 1 person to create the space for
    if len(ids)>1:
        # now we need to retrieve the AppAdmin access token since it is the fully licensed user that can create
        # the spaces to add the guest token users in so that they can message and meet with each other without
        # incurring into any licensing violations
        api = WebexTeamsAPI(access_token=ACCESS_TOKEN)
        # below we are using a very crude way to give unique names to the spaces: "guestconn" plus the last 4 characters of
        # the person ID of each of the participants. It is reccomended you implement a more "user friendly" naming scheme
        roomname="guestconn"
        for the_id in ids:
            roomname=roomname+the_id[-4:]
        #now it is time to first just create the new space and capture it's ID
        the_room=api.rooms.create(roomname)
        print("Created room ID: ",the_room.id)

        # now iterate through all the personIDs that we intend to put in a space and add them by creating
        # a new "membership"  in the new space using it's ID we obtained above after creating
        for the_id in ids:
            the_membership=api.memberships.create(the_room.id,the_id)
            print("Created a membership: ",the_membership.id)
    else:
        print("Need at least 2 ids to connect in a space.")
    return "200"

@app.route('/swap_big_space', methods=["POST"])
def swap_big_space():
    # Here we need the space ID to go ahead and select a "free" space from the largespaces array of dicts (which was read
    # originally from largespaces.json upon starting the app, for now it does not update the file)
    # and mark that space as busy. We need to remove all memberships execpt AppAdmin and the owner from it in case it was not
    # properly "cleaned out" in the previous use.
    # Afterwards, we read the members of the large space still being displayed on the Guest page and create new
    # memberships with them in the reserved large space. After that, we can return the space ID of the "reserved" large space
    # so the guest page redraws the widget without the restrictions and let's people meet in that space.

    global largespaces, AppAdminID

    orig_big_space_id = request.form['room_id']
    print("Orig big space ID: ",orig_big_space_id)

    reserved_space_id=''

    for largespace in largespaces:
        if not largespace['busy']:
            #first capture the space id we are going to reserve and mark it as busy. Also associate
            #it with the space being swapped out
            print("Reserving space: ",largespace['name']," with space id: ",largespace['id'])
            reserved_space_id=largespace['id']
            largespace['busy']=True
            largespace['borrowing_space_id'] = orig_big_space_id

            #now clean it up in case there were still members on it besides AppAdmin and the owner.
            api = WebexTeamsAPI(access_token=ACCESS_TOKEN)
            reserved_existing_members=api.memberships.list(reserved_space_id)
            print("Checking for stragglers in large space that is free.....")
            for existing_member in reserved_existing_members:
                print("Evaluating membership: ",existing_member)
                print("Display name: ", existing_member.personDisplayName)
                if existing_member.personId!=AppAdminID and existing_member.personId!=largespace['ownerId']:
                    print("Removing member in supposedly free large space: ",existing_member.personDisplayName)
                    api.memberships.delete(existing_member.id)

            #next we populate the reserved large space with members of the original space, except AppAdmin who is already there
            print("Populating reserved space with members from original space...")
            orig_big_space_members = api.memberships.list(orig_big_space_id)
            for orig_member in orig_big_space_members:
                if orig_member.personId!=AppAdminID:
                    api.memberships.create(reserved_space_id,orig_member.personId)
                    print("added: ",orig_member.personDisplayName)

            break

    if reserved_space_id=='':
        print("All large spaces are busy!")
        data = {'message': 'No large spaces available', 'reserved_space_id': reserved_space_id}
        return make_response(jsonify(data), 500)
    else:
        print("Reserved space id: ", reserved_space_id)
        data = {'message': 'Reserved', 'reserved_space_id': reserved_space_id}
        return make_response(jsonify(data), 201)





@app.route('/return_big_space', methods=["POST"])
def return_big_space():
    # this should be called when a large meeting is over, for now, when one of the participants hits a custom "end" button on the page
    # For now it might error out if there are still people meeting since we should not be able to remove membership in the middle of a call,
    # but we will try anyhow.
    # To start, we need to receive the large "borrowed" space ID to go ahead and remove it's members except the owner and AppAdmin, then mark it in
    # largespaces.json as free and write the file back out
    # then, we need to return to the calling Ajax function the space ID of the original space so it can be shown again with the "custom" call button

    global largespaces, AppAdminID

    #reserved_space_id = request.form['reserved_space_id']
    orig_big_space_id= request.form['orig_big_space_id']

    print("Returning big space that replaced original: ", orig_big_space_id)


    #print("Reserved space ID to return: ", reserved_space_id)

    reserved_space_id=''

    for largespace in largespaces:
        if largespace['borrowing_space_id']==orig_big_space_id:
            # first get back the borrowing space id and mark this large space as free.
            #
            print("Returning space: ", largespace['name'], " with space id: ", largespace['id'])
            reserved_space_id = largespace['id']
            largespace['busy'] = False
            largespace['borrowing_space_id'] = ''

            # now clean it up since it is no longer being used
            api = WebexTeamsAPI(access_token=ACCESS_TOKEN)
            reserved_existing_members = api.memberships.list(reserved_space_id)
            print("Removing members from space we just freed.....")
            for existing_member in reserved_existing_members:
                if existing_member.personId != AppAdminID and existing_member.personId != largespace['ownerId']:
                    print("Removing member from the space: ", existing_member.personDisplayName)
                    api.memberships.delete(existing_member.id)
            break

    if reserved_space_id=='':
        #return error
        data = {'message': 'Could not return reserved large room', 'reserved_space_id': reserved_space_id}
        return make_response(jsonify(data), 500)
    else:
        data = {'message': 'Returned to pool', 'reserved_space_id': reserved_space_id}
        return make_response(jsonify(data), 201)

#Main Function
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)

