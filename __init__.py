from __future__ import print_function
from adapt.intent import IntentBuilder
from mycroft.skills.core import MycroftSkill, intent_handler
from mycroft.util.log import LOG
from mycroft.util.parse import extract_datetime
from datetime import datetime, timedelta
import pickle
import os.path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import httplib2
from googleapiclient.discovery import build
from oauth2client.file import Storage
from oauth2client.client import OAuth2WebServerFlow
from oauth2client import tools
import string
import pytz
UTC_TZ = u'+00:00'
SCOPES = ['https://www.googleapis.com/auth/calendar']
FLOW = OAuth2WebServerFlow(
    client_id='73558912455-mcb8cb7llg1bh84hls74257utt44rmlp.apps.googleusercontent.com',
    client_secret='8YYYAuCbspk1FzQZB75KSzvF',
    scope='https://www.googleapis.com/auth/contacts.readonly',
    user_agent='Smart assistant box')

class CreateEvent(MycroftSkill):

    # The constructor of the skill, which calls MycroftSkill's constructor
    def __init__(self):
        super(CreateEvent, self).__init__(name="CreateEvent")

    @property
    def utc_offset(self):
        return timedelta(seconds=self.location['timezone']['offset'] / 1000)

    @intent_handler(IntentBuilder("").require("create_event"))
    def createEventt(self):
        creds = None
        # The file token.pickle stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)       #dans mycroft on met '/opt/mycroft/skills/createeventskill.hanabouzid/credentials.json'
                creds = flow.run_local_server(port=0)
                # Save the credentials for the next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        service = build('calendar', 'v3', credentials=creds)

        # Call the Calendar API
        now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        print('Getting the upcoming 10 events')
        events_result = service.events().list(calendarId='primary', timeMin=now,
                                              maxResults=10, singleEvents=True,
                                              orderBy='startTime').execute()
        events = events_result.get('items', [])

        if not events:
            print('No upcoming events found.')
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            print(start, event['summary'])

        storage = Storage('info.dat')
        credentials = storage.get()
        if credentials is None or credentials.invalid == True:
            credentials = tools.run_flow(FLOW, storage)
        # Create an httplib2.Http object to handle our HTTP requests and
        # authorize it with our good Credentials.
        http = httplib2.Http()
        http = credentials.authorize(http)
        # Build a service object for interacting with the API. To get an API key for
        # your application, visit the Google API Console
        # and look at your application's credentials page.
        people_service = build(serviceName='people', version='v1', http=http)
        # To get a list of people in the user's contacts,
        results = people_service.people().connections().list(resourceName='people/me', pageSize=100,
                                                             personFields='names,emailAddresses',
                                                             fields='connections,totalItems,nextSyncToken').execute()
        connections = results.get('connections', [])
        #need to verify this
        #self.speak(connections)
        #get informations about the event
        tittle = self.get_response("what is the name of the event")
        description = self.get_response("can you describe more the event")
        strtdate = self.get_response("when the event starts")
        st = extract_datetime(strtdate)
        enddate = self.get_response("when the event ends")
        et = extract_datetime(enddate)
        st = st[0] - self.utc_offset
        et = et[0] - self.utc_offset
        datestart = st.strftime('%Y-%m-%dT%H:%M:00')
        datend = et.strftime('%Y-%m-%dT%H:%M:00')
        datend += UTC_TZ
        datestart += UTC_TZ

        #adding attendees
        # getting contacts emails and names in two lists nameliste and adsmails
        nameListe = []
        adsmails = []
        #attendee est la liste des invités qui sont disponibles
        attendee=[]

        for person in connections:
            emails = person.get('emailAddresses', [])
            names = person.get('names', [])
            adsmails.append(emails[0].get('value'))
            nameListe.append(names[0].get('displayName'))
        #verify if the attendee in the connection liste and if he is free
        confirm= self.get_response("Do you want to invite someone? yes or no?")
        if confirm =='yes':
            n_attendee = self.get_response(" how many persons would you like to invite")
            n = int(n_attendee )
            print(n)
            j = 0
            while j < n:
                exist = False
                x = self.get_response("who do you want to invite")
                for l in range(0,len(nameListe)):
                    if x == nameListe[l]:
                        self.speak_dialog("exist")
                        exist = True
                        mail = adsmails[l]
                        attendee.append(mail)
                        # on va verifier la disponibilité de chaque invité
                        body = {
                            "timeMin": datestart,
                            "timeMax": datend,
                            "timeZone": 'America/Los_Angeles',
                            "items": [{"id":mail}]
                        }
                        eventsResult = service.freebusy().query(body=body).execute()
                        cal_dict = eventsResult[u'calendars']
                        print(cal_dict)
                        for cal_name in cal_dict:
                            print(cal_name, ':', cal_dict[cal_name])
                            statut = cal_dict[cal_name]
                            for i in statut:
                                if (i == 'busy' and statut[i] == []):
                                    self.speak_dialog("free")
                                    #ajouter l'email de x ala liste des attendee
                                elif (i == 'busy' and statut[i] != []):
                                    self.speak_dialog("busy")

                if exist == False:
                    self.speak_dialog("notexist")
                j += 1

        attendeess = []
        for i in range(len(attendee)):
            email = {'email': attendee[i]}
            attendeess.append(email)
        notification = self.get_response('would you like to send notification to attendees?')
        if notification == 'yes':
            notif = True,
        else:
            notif = False
        #liste des emails de toutes les salles de focus
        freemails=[]
        freerooms = []
        nameroom =["Midoune Meeting Room","Aiguilles Meeting Room","Barrouta Meeting Room","Kantaoui Meeting Room","Gorges Meeting Room","Ichkeul Meeting Room","Khemir Meeting Room","Tamaghza Meeting Room","Friguia Meeting Room","Ksour Meeting Room","Medeina Meeting Room","Thyna Meeting Room"]
        emailroom=["focus-corporation.com_3436373433373035363932@resource.calendar.google.com","focus-corporation.com_3132323634363237333835@resource.calendar.google.com","focus-corporation.com_3335353934333838383834@resource.calendar.google.com","focus-corporation.com_3335343331353831343533@resource.calendar.google.com","focus-corporation.com_3436383331343336343130@resource.calendar.google.com","focus-corporation.com_36323631393136363531@resource.calendar.google.com","focus-corporation.com_3935343631343936373336@resource.calendar.google.com","focus-corporation.com_3739333735323735393039@resource.calendar.google.com","focus-corporation.com_3132343934363632383933@resource.calendar.google.com","focus-corporation.com_@resource.calendar.google.com", "focus-corporation.com_@resource.calendar.google.com","focus-corporation.com_@resource.calendar.google.com"]
        for i in range(0, len(emailroom)):
            body = {
                "timeMin": datestart,
                "timeMax": datend,
                "timeZone": 'America/Los_Angeles',
                "items": [{"id": emailroom[i]}]
            }
            roomResult = service.freebusy().query(body=body).execute()
            room_dict = roomResult[u'calendars']
            for cal_room in room_dict:
                print(cal_room, ':', room_dict[cal_room])
                case = room_dict[cal_room]
                for j in case:
                    if (j == 'busy' and case[j] == []):
                        # la liste freerooms va prendre  les noms des salles free
                        freerooms.append(nameroom[i])
                        freemails.append(emailroom[i])

        reservation = self.get_response('do you need to make a reservation for a meeting room? Yes or No?')
        if reservation == 'yes':
            s = ",".join(freerooms)
            #print("les salles disponibles a cette date sont", freerooms)
            self.speak_dialog("freerooms",data={"s":s})
            room = self.get_response('which Room do you want to make a reservation for??')
            for i in range(0, len(freerooms)):
                if (freerooms[i] == room):
                    #ajouter l'email de room dans la liste des attendees
                    attendeess.append({'email': freemails[i]})

        #creation d'un evenement
        event = {
            'summary': tittle,
            'location': room,
            'description': description,
            'start': {
                'dateTime': datestart,
                'timeZone': 'America/Los_Angeles',
            },
            'end': {
                'dateTime': datend,
                'timeZone': 'America/Los_Angeles',
            },
            'recurrence': [
                'RRULE:FREQ=DAILY;COUNT=1'
            ],
            'attendees': attendeess,
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 10},
                ],
            },
        }
        event = service.events().insert(calendarId='primary',sendNotifications=notif, body=event).execute()
        print('Event created: %s' % (event.get('htmlLink')))
        self.speak_dialog("eventCreated")
def create_skill():
    return CreateEvent()
