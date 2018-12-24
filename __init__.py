# Copyright 2018 Astromechs, #3409
#
# Copyright 2017, Mycroft AI Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import time
from threading import Thread

from adapt.intent import IntentBuilder
from mycroft.messagebus.message import Message
from mycroft.skills.core import MycroftSkill, intent_handler
from mycroft.audio import wait_while_speaking
from mycroft.util.parse import extractnumber, fuzzy_match
from mycroft.util.format import pronounce_number

from mycroft.util import LOG

import requests
import re
from bs4 import BeautifulSoup

#######################################################################


class AstromechPit(MycroftSkill):
    def __init__(self): 
        super(AstromechPit, self).__init__("AstromechPit") 
        self.playing = False 

    def initialize(self):   
        self.log.debug("================================")
        self.log.debug("Initializing...")
    
        # Listen for the message send by the DEMO menu item on a Mark 1
        self.add_event("mycroft.mark1.demo", self.start_DEMO, False)
        # self.add_event("mycroft.volume.increase", self._trigger_speech, False) 
        # self.add_event("mycroft.stop", self._trigger_speech, False)
        self.log.debug("================================")  
        self.log.debug("Connecting to MoFTC Scores")
        self.externalScoring = ExternalScoring("http://houston.worlds.pennfirst.org/cache/TeamInfo_2018_World_Championship_Jemison.html",
                                               "http://houston.worlds.pennfirst.org/cache/TeamInfo_2018_World_Championship_Franklin.html",
                                               # self.settings["URL1"], # DIVISION 1
                                               # self.settings["URL2"],  # DIVISION 2
                                               self.settings["api_key"])  # API KEY
        #   Check to see if we can get data from the external system.  Any failure on this initial connection
        #   and we'll give the user an error.
        #try: 
        self.event1, self.teams1, self.matches1 = self.externalScoring.getEventTeamsMatches()
        self.externalScoring.changeDivisions()
        self.event2, self.teams2, self.matches2 = self.externalScoring.getEventTeamsMatches()

        self.schedule_repeating_event(self.handle_update, 0, 15)

    @intent_handler(IntentBuilder("").require("Introduce"))
    def handle_introduction(self, message):
        self.speak("I was a donation from the tech start up Mycroft A.I.") 
        self.speak("The Astromechs are turning me into an outreach robot.") 
        
    @intent_handler(IntentBuilder("").require("Query").require("Team"))
    def handle_team_query(self, message):    
        teamNum = int(extractnumber(message.data["utterance"]))
        teamLower = teamNum % 100  # 4
        teamUpper = (teamNum - teamLower) / 100  # 4
        if (teamLower > 9): 
            speak = pronounce_number(int(teamUpper)) + " " + pronounce_number(int(teamLower))
        else:
            speak = pronounce_number(int(teamUpper)) + " oh " + pronounce_number(int(teamLower))
        
        self.log.debug("Team #:" + str(teamNum)) 
        if teamNum in self.teams1: 
            speechData = {
                "num": self.teams1[teamNum]["number"],
                "name": self.teams1[teamNum]["name"],
                "rank": self.teams1[teamNum]["rank"],
                "div": self.event1["subtitle"], 
                "ps": int(self.teams1[teamNum]["powerScore"]) 
            }
            self.speak_dialog("team.info", speechData)

        else: 
            if teamNum in self.teams2:
                speechData = {
                    "num": self.teams2[teamNum]["number"],
                    "name": self.teams2[teamNum]["name"],
                    "rank": self.teams2[teamNum]["rank"],
                    "div": self.event2["subtitle"], 
                    "ps": int(self.teams2[teamNum]["powerScore"]) 
                }
                self.speak_dialog("team.info", speechData)
            else:
                self.speak("I don't know them.")
    def start_DEMO(self, message):
        # This triggers when DEMO is picked from the menu
        self.schedule_repeating_event(self._timed_speech,
                                      None, 60*5,  # 5 minutes
                                      name='TimedSpeech')
    def handle_update(self, message):
        # This is a sheduled repeating event
        self.log.debug("beginning update")
        self.event1, self.teams1, self.matches1 = self.externalScoring.getEventTeamsMatches()
        self.externalScoring.changeDivisions()
        self.event2, self.teams2, self.matches2 = self.externalScoring.getEventTeamsMatches()
        self.log.debug("update finished")



    def _timed_speech(self, message=None):
        self.log.info("RUNNING:  _timed_speech")
        if self.playing: 
            self.log.info("skipped") 
            return  # skip 

        self.log.info("Doing the spiel")
        self.playing = True 
        self.speak("Hello, I'm Mycroft. If you would like to learn more about the Astromechs, " +
                   "team 34 oh 9, press my button, or ask a friendly team member.")
        wait_while_speaking()
        self.playing = False

    ######################################################################
        
    def _trigger_speech(self, message=None):
        self.playing = True 
        self.cancel_scheduled_event('TriggerSpeech')
        # self.enclosure.eyes_reset()
        self.speak("I'm Mycroft, the robotic team member of the Astromechs," + 
                   "team 34 oh 9.  We are from Kansas City, Missouri, and have been a team for " +
                   "ten years. Today, we have 8 FTC students and 4 FLL students.")
        self.speak("At the Missouri State Championship, we were the Inspire Award winners and " +
                   "the first pick of the winning alliance. Please take a tattoo, button, or wristband.")
        wait_while_speaking()
        self.playing = False

    def xxxstop(self):
        if self.playing:
            self.playing = False  # the thread will kill itself
            self.enclosure.eyes_reset()
            return True
        else:
            # Kick off a speech 
            self.schedule_repeating_event(self._trigger_speech,
                                          None, 1,
                                          name='TriggerSpeech')
            return False

'''
IMPORTANT NOTE

There are three dictionary objects that will be used throughout the code: event, teams, matches
Ideally these three objects would be well defined in class definitions, but that's something to
do in the future.  For now, we'll just document what they look like.

Here are short examples of each, with indentation for clarity.  Note that matches will ONLY include qualification matches, so
only two teams are supported.  We exclude elim matches because we can't know for sure which teams actually played.

event = {'title': 'Southeast Missouri State University Qualifier', 'subtitle': ''}

teams = {   406:
                {'number': 406, 'name': "Richard's Fine Men", 'school': 'Parkway South High', 'city': 'Manchester',
                 'state': 'MO', 'country': '', 'rank': 8, 'qp': 6, 'rp': 451, 'highest': 289, 'matches': 5,
                 'real_matches': 5, 'allianceScore': 87.1, 'powerScore': 113.59381059999865},
            3620: {'number': 3620, 'name': 'Furious George', ...
            ...
        }

matches =   {   1:
                {'matchid': 1,
                    'alliances': {  'red': {'team1': 7469, 'team2': 406, 'total': 203, 'auto': 55, 'teleop': 128, 'endg': 20, 'pen': 0},
                                    'blue': {'team1': 13616, 'team2': 9905, 'total': 116, 'auto': 60, 'teleop': 36, 'endg': 20, 'pen': 0}
                                 }
                },
                2: {'matchid': 2, 'alliances': ...
                ...
            }

'''


#
# ExternalScoring
#
# This encapsulates the logic for retrieving data from the remote server, as well as the calculation of the current PowerScores
#
# event, teams, and matches dictionary objects are constructed from remote data in these methods
#
class ExternalScoring:
    # Constructor
    def __init__(self,division1URI,division2URI,apiKey):
        self.division1URI = ""
        self.division2URI = ""
        self.setAPIKey(apiKey)
        self.numDivisions = 0
        self.currentDivision = 0
        self.setURIs(division1URI,division2URI)

    def setAPIKey(self, apiKey):
        self.apiKey = apiKey

    # Set the URI's
    def setURIs(self, division1URI, division2URI):
        self.division1URI=division1URI
        self.division2URI=division2URI

        # Do a replacement if the url seems to be for ftcscores.com
        #    https://ftcscores.com/event/huD_6Ue9 is an example ftcscores URL
        #    https://api.ftcscores.com/api/events/huD_6Ue9 is the corresponding api URL
        # Note: no effect if the api url was used, or if the url is not for ftcscores.com
        self.division1URI = self.division1URI.replace("https://ftcscores.com/event/", "https://api.ftcscores.com/api/events/")
        self.division2URI = self.division2URI.replace("https://ftcscores.com/event/", "https://api.ftcscores.com/api/events/")

        # Do a replacement if the url seems to be for theorangealliance.org
        #    https://theorangealliance.org/events/1718-MO-CAPS is an example ftcscores URL
        #    https://theorangealliance.org/apiv2/event/1718-MO-CAPS is the corresponding event api URL
        # Note: no effect if the api url was used, or if the url is not for ftcscores.com
        self.division1URI = self.division1URI.replace("https://theorangealliance.org/events/", "https://theorangealliance.org/apiv2/event/")
        self.division2URI = self.division2URI.replace("https://theorangealliance.org/events/", "https://theorangealliance.org/apiv2/event/")

        if (self.division2URI == ""):
            self.numDivisions=1
            self.currentDivision=1

        else:
            self.numDivisions=2
            self.currentDivision=1

    # get the URI for the current division
    def getCurrentDivisionURI(self):
        if (self.currentDivision==1):
            return self.division1URI
        else:
            return self.division2URI

    # change the division
    def changeDivisions(self):
        if (self.currentDivision==1 and self.numDivisions==2):
            self.currentDivision=2
        else:
            self.currentDivision=1

    # Get the data from the extenral system ... includes calculating powerscores
    def getEventTeamsMatches(self):

        event = {}
        teams = {}
        matches = {}

        requestURI = self.getCurrentDivisionURI()

        if "api.ftcscores.com" in requestURI:
            # Specific logic for ftcscores.com
            event, teams, matches = self.getEventTeamsMatches_ftcscores()

        elif "theorangealliance.org/apiv2" in requestURI:
            # Specific logic for theorangealliance
            event, teams, matches = self.getEventTeamsMatches_toa()

        elif "worlds.pennfirst.org/cache/TeamInfo" in requestURI:
            event, teams, matches = self.getEventTeamsMatches_pennfirst()

        else:
            # Default logic - ftc scoring system
            event, teams, matches = self.getEventTeamsMatches_default()

        # Now update powerscores
        self.__calculatePowerScore(teams, matches)
        LOG.debug("powerscore calculated")
        
        return (event, teams, matches)


    # Get data from ftcscores
    def getEventTeamsMatches_ftcscores(self):

        requestURI = self.getCurrentDivisionURI()

        event = {}
        teams = {}
        matches = {}
        
        LOG.debug("request starting ...")
        r=requests.get(requestURI, timeout=5)
        jsonResult = r.json()
        LOG.debug("request finished")

        # Just a couple of event things
        event['title'] = jsonResult['fullName']
        event['subtitle'] = ""
        if "subtitle" in jsonResult:
            event['subtitle'] = jsonResult['subtitle']
    
        # Assemble all the team info from the teams and rankings sections
        if "teams" in jsonResult:
            for team in jsonResult["teams"]:
                teamNum = jsonResult["teams"][team]["number"]
                teams[teamNum] = {}
                teams[teamNum]['number'] = teamNum
                teams[teamNum]['name'] = jsonResult["teams"][team]["name"]
                teams[teamNum]['school'] = jsonResult["teams"][team]["school"]
                teams[teamNum]['city'] = jsonResult["teams"][team]["city"]
                teams[teamNum]['state'] = jsonResult["teams"][team]["state"]
                teams[teamNum]['country'] = jsonResult["teams"][team]["country"]
        if "rankings" in jsonResult:
            for ranking in jsonResult["rankings"]:
                teamNum = ranking["number"]
                teams[teamNum]['rank'] = ranking["rank"]
                teams[teamNum]['qp'] = ranking["current"]["qp"]
                teams[teamNum]['rp'] = ranking["current"]["rp"]
                teams[teamNum]['highest'] = ranking["current"]["highest"]
                teams[teamNum]['matches'] = ranking["current"]["matches"]
                teams[teamNum]['real_matches'] = 0
                teams[teamNum]['allianceScore'] = 0
                teams[teamNum]['powerScore'] = 0


        # Now grab the matches, we want completed qualifier matches only
        if "rankings" in jsonResult:
            for match in jsonResult["matches"]:
                if ((match["number"].startswith("Q")) and (match["status"]=="done")):
                    matches[match["number"]] = {}
                    matches[match["number"]]['matchid'] = match["number"]
                    matches[match["number"]]['alliances'] = {}

                    matches[match["number"]]['alliances']['red'] = {}
                    matches[match["number"]]['alliances']['red']['team1'] = match["teams"]['red'][0]['number']
                    matches[match["number"]]['alliances']['red']['team2'] = match["teams"]['red'][1]['number']
                    matches[match["number"]]['alliances']['red']['total'] = match["scores"]['red']
                    matches[match["number"]]['alliances']['red']['auto'] = match["subscoresRed"]['auto']
                    matches[match["number"]]['alliances']['red']['teleop'] = match["subscoresRed"]['tele']
                    matches[match["number"]]['alliances']['red']['endg'] = match["subscoresRed"]['endg']
                    matches[match["number"]]['alliances']['red']['pen'] = match["subscoresRed"]['pen']
                    #also... udpate the "real matches"... to account for surrogates in powerscore
                    teams[match["teams"]['red'][0]['number']]['real_matches']+=1
                    teams[match["teams"]['red'][1]['number']]['real_matches']+=1

                    matches[match["number"]]['alliances']['blue'] = {}
                    matches[match["number"]]['alliances']['blue']['team1'] = match["teams"]['blue'][0]['number']
                    matches[match["number"]]['alliances']['blue']['team2'] = match["teams"]['blue'][1]['number']
                    matches[match["number"]]['alliances']['blue']['total'] = match["scores"]['blue']
                    matches[match["number"]]['alliances']['blue']['auto'] = match["subscoresBlue"]['auto']
                    matches[match["number"]]['alliances']['blue']['teleop'] = match["subscoresBlue"]['tele']
                    matches[match["number"]]['alliances']['blue']['endg'] = match["subscoresBlue"]['endg']
                    matches[match["number"]]['alliances']['blue']['pen'] = match["subscoresBlue"]['pen']
                    #also... udpate the "real matches"... to account for surrogates in powerscore
                    teams[match["teams"]['blue'][0]['number']]['real_matches']+=1
                    teams[match["teams"]['blue'][1]['number']]['real_matches']+=1
            LOG.debug("data compiled")
        return (event, teams, matches)

    # Get data from theorangealliance
    def getEventTeamsMatches_toa(self):

        requestURI = self.getCurrentDivisionURI()

        event = {}
        teams = {}
        matches = {}

        # why, oh why, does toa make getting the event details so hard.  5 requests are necessary to get the data we need :(
        r=requests.get(requestURI, headers={'X-Application-Origin': 'PowerScore', 'X-TOA-Key': self.apiKey},  timeout=5)
        eventJsonResult = r.json()

        r=requests.get(requestURI+"/matches", headers={'X-Application-Origin': 'PowerScore', 'X-TOA-Key': self.apiKey},  timeout=5)
        matchesJsonResult = r.json()

        r=requests.get(requestURI+"/matches/stations", headers={'X-Application-Origin': 'PowerScore', 'X-TOA-Key': self.apiKey},  timeout=5)
        stationsJsonResult = r.json()

        r=requests.get(requestURI+"/teams", headers={'X-Application-Origin': 'PowerScore', 'X-TOA-Key': self.apiKey},  timeout=5)
        teamsJsonResult = r.json()

        r=requests.get(requestURI+"/rankings", headers={'X-Application-Origin': 'PowerScore', 'X-TOA-Key': self.apiKey},  timeout=5)
        rankingsJsonResult = r.json()


        # Just a couple of event things
        event['title'] = eventJsonResult[0]['event_name']
        event['subtitle'] = ""
        if "division_name" in eventJsonResult:
            event['subtitle'] = eventJsonResult[0]['division_name']

        # Assemble all the team info from the teams request
        for team in teamsJsonResult:
            teamNum = int(team["team_key"])
            teams[teamNum] = {}
            teams[teamNum]['number'] = teamNum
            teams[teamNum]['name'] = team["team_name_short"]
            teams[teamNum]['school'] = ''
            teams[teamNum]['city'] = team["city"]
            teams[teamNum]['state'] = team["state_prov"]
            teams[teamNum]['country'] = team["country"]

        # Add in the ranking information
        for ranking in rankingsJsonResult:
            teamNum = int(ranking["team_key"])
            teams[teamNum]['rank'] = ranking["rank"]
            teams[teamNum]['qp'] = ranking["qualifying_points"]
            teams[teamNum]['rp'] = ranking["ranking_points"]
            teams[teamNum]['highest'] = ranking["highest_qual_score"]
            teams[teamNum]['matches'] = ranking["played"]
            teams[teamNum]['real_matches'] = 0
            teams[teamNum]['allianceScore'] = 0
            teams[teamNum]['powerScore'] = 0


        # Now build up the qualifier matches
        for match in matchesJsonResult:

            # This seems to mark a qualifier match, but they haven't documented it
            # Still have no idea how an upcoming match is delineated... so making best guess
            if ((match["tournament_level"]==1) and (match["blue_score"]!=None)):
                matches[match["match_key"]] = {}
                matches[match["match_key"]]['matchid'] = match["match_key"]
                matches[match["match_key"]]['alliances'] = {}

                matches[match["match_key"]]['alliances']['red'] = {}
                matches[match["match_key"]]['alliances']['red']['total'] = match["red_score"]
                matches[match["match_key"]]['alliances']['red']['auto'] = match["red_auto_score"]
                matches[match["match_key"]]['alliances']['red']['teleop'] = match["red_tele_score"]
                matches[match["match_key"]]['alliances']['red']['endg'] = match["red_end_score"]
                matches[match["match_key"]]['alliances']['red']['pen'] = match["blue_penalty"]


                matches[match["match_key"]]['alliances']['blue'] = {}
                matches[match["match_key"]]['alliances']['blue']['total'] = match["blue_score"]
                matches[match["match_key"]]['alliances']['blue']['auto'] = match["blue_auto_score"]
                matches[match["match_key"]]['alliances']['blue']['teleop'] = match["blue_tele_score"]
                matches[match["match_key"]]['alliances']['blue']['endg'] = match["blue_end_score"]
                matches[match["match_key"]]['alliances']['blue']['pen'] = match["red_penalty"]

        # Now, going through the "stations" to pick up the teams for the match.
        # Would have been nice it could have been included in the matches reponse...  oh well
        for station in stationsJsonResult:
            if (station["match_key"] in matches):

                # red teams
                matches[station["match_key"]]['alliances']['red']['team1'] = int(station["teams"].split(",")[0])
                matches[station["match_key"]]['alliances']['red']['team2'] = int(station["teams"].split(",")[1])
                #also... udpate the "real matches"... to account for surrogates in powerscore
                teams[int(station["teams"].split(",")[0])]['real_matches']+=1
                teams[int(station["teams"].split(",")[1])]['real_matches']+=1

                # blue teams
                matches[station["match_key"]]['alliances']['blue']['team1'] = int(station["teams"].split(",")[2])
                matches[station["match_key"]]['alliances']['blue']['team2'] = int(station["teams"].split(",")[3])
                #also... udpate the "real matches"... to account for surrogates in powerscore
                teams[int(station["teams"].split(",")[2])]['real_matches']+=1
                teams[int(station["teams"].split(",")[3])]['real_matches']+=1

        return (event, teams, matches) 

    def getEventTeamsMatches_default(self):
        requestURI = self.getCurrentDivisionURI()
        return self.getEventTeamsMatches_ScoringURLs(requestURI+"/TeamList",  requestURI+"/Rankings", requestURI+"/MatchDetails")

    def getEventTeamsMatches_pennfirst(self):
        requestURI = self.getCurrentDivisionURI()
        p = re.compile('(http://.*/cache/)TeamInfo(.*\.html).*')
        m = p.match(requestURI)

        teamListURL = m.group(1)+'TeamInfo'+m.group(2)
        rankingsURL = m.group(1)+'Rankings'+m.group(2)
        matchDetailsURL = m.group(1)+'MatchResultsDetails'+m.group(2)

        return self.getEventTeamsMatches_ScoringURLs(teamListURL, rankingsURL, matchDetailsURL)


    # Get the data the default way ... e.g. from the socring software
    def getEventTeamsMatches_ScoringURLs(self, teamListURL, rankingsURL, matchDetailsURL):

        event = {}
        teams = {}
        matches = {}

        # Not one of the specific known use cases ... so try as though it's the scoring software
        r=requests.get(teamListURL, timeout=3)
        teamListHTML = r.text
        teamList = BeautifulSoup(teamListHTML, "html.parser")

        r=requests.get(rankingsURL, timeout=3)
        rankingsHTML = r.text
        rankings = BeautifulSoup(rankingsHTML,"html.parser")

        r=requests.get(matchDetailsURL, timeout=3)
        matchDetailsHTML = r.text
        matchDetails = BeautifulSoup(matchDetailsHTML,"html.parser")

        # If we got here without failing, then we probably have a good set of data

        h2 = teamList.html.center.h2
        # Just a couple of event things
        event['title'] = h2.contents[0]
        event['subtitle'] = ""
        if (len(h2.contents)>3):
            event['subtitle'] = h2.contents[2].lstrip()

        # Get teams from the team list
        i=0
        for tr in  teamList.html.div.table.find_all("tr"):
            i+=1
            if i>1:
                teamNum = int(tr.contents[0].string)
                teams[teamNum] = {}
                teams[teamNum]['number'] = teamNum
                teams[teamNum]['name'] = tr.contents[1].string
                teams[teamNum]['school'] = tr.contents[2].string
                teams[teamNum]['city'] = tr.contents[3].string
                teams[teamNum]['state'] = tr.contents[4].string
                teams[teamNum]['country'] = tr.contents[5].string
        # Add in the Ranking info
        i=0
        for tr in  rankings.html.div.table.find_all("tr"):
            i+=1
            if i>1:
                teamNum = int(tr.contents[1].string)
                teams[teamNum]['rank'] = int(tr.contents[0].string)
                teams[teamNum]['qp'] = int(tr.contents[3].string)
                teams[teamNum]['rp'] = int(tr.contents[4].string)
                teams[teamNum]['highest'] = int(tr.contents[5].string)
                teams[teamNum]['matches'] = int(tr.contents[6].string)
                teams[teamNum]['real_matches'] = 0
                teams[teamNum]['allianceScore'] = 0
                teams[teamNum]['powerScore'] = 0

        # Now grab the matches, we want completed qualifier matches only
        i=0
        for tr in  matchDetails.html.div.table.find_all("tr"):
            i+=1
            if i>2:
                if (("-" in tr.contents[1].string) and ("Q" in tr.contents[0].string)):
                    # A dash in the score column means we have a score, so the match has been played
                    # A Q in the first column means it's a qualifier match
                    matchNum = int(tr.contents[0].string.split("-")[1])
                    matches[matchNum] = {}
                    matches[matchNum]['matchid'] = matchNum
                    matches[matchNum]['alliances'] = {}

                    matches[matchNum]['alliances']['red'] = {}
                    matches[matchNum]['alliances']['red']['team1'] = int(tr.contents[2].string.split()[0].replace("*",""))
                    matches[matchNum]['alliances']['red']['team2'] = int(tr.contents[2].string.split()[1].replace("*",""))
                    matches[matchNum]['alliances']['red']['total'] = int(tr.contents[4].string)
                    matches[matchNum]['alliances']['red']['auto'] = int(tr.contents[5].string)
                    matches[matchNum]['alliances']['red']['teleop'] = int(tr.contents[7].string)
                    matches[matchNum]['alliances']['red']['endg'] = int(tr.contents[8].string)
                    matches[matchNum]['alliances']['red']['pen'] = int(tr.contents[9].string)
                    #also... udpate the "real matches"... to account for surrogates in powerscore
                    teams[int(tr.contents[2].string.split()[0].replace("*",""))]['real_matches']+=1
                    teams[int(tr.contents[2].string.split()[1].replace("*",""))]['real_matches']+=1

                    matches[matchNum]['alliances']['blue'] = {}
                    matches[matchNum]['alliances']['blue']['team1'] = int(tr.contents[3].string.split()[0].replace("*",""))
                    matches[matchNum]['alliances']['blue']['team2'] = int(tr.contents[3].string.split()[1].replace("*",""))
                    matches[matchNum]['alliances']['blue']['total'] = int(tr.contents[10].string)
                    matches[matchNum]['alliances']['blue']['auto'] = int(tr.contents[11].string)
                    matches[matchNum]['alliances']['blue']['teleop'] = int(tr.contents[13].string)
                    matches[matchNum]['alliances']['blue']['endg'] = int(tr.contents[14].string)
                    matches[matchNum]['alliances']['blue']['pen'] = int(tr.contents[15].string)
                    #also... udpate the "real matches"... to account for surrogates in powerscore
                    teams[int(tr.contents[3].string.split()[0].replace("*",""))]['real_matches']+=1
                    teams[int(tr.contents[3].string.split()[1].replace("*",""))]['real_matches']+=1

        return (event, teams, matches)


    # update the PowerScore data for the teams dict object
    def __calculatePowerScore(self,teams, matches):
        #
        # FINALLY - THIS IS IT!  This is the PowerScore Calculation.  Short and sweet.
        #
        # Does not explicitly return anything.  This updates each teams dictionary object with PowerScores.
        #   This code is separated out only for clarity.
        #

        # Get the alliance scores set up
        allianceScores = {}
        for teamNum in teams:
            allianceScores[teamNum] = 0.;

        # Now do the allianceScores total
        for matchid in matches:
            match = matches[matchid]

            adjBlueScore = match["alliances"]["blue"]["total"]-match["alliances"]["blue"]["pen"]
            adjRedScore = match["alliances"]["red"]["total"]-match["alliances"]["red"]["pen"]

            # The math here takes care of the 50-50 split - each team in an alliance get credit for 50% of the scoring (we'll fix that later)
            # There's also a division by the number of matches for each team ... this has the effect of normalizing to the number of matches played
            teams[match["alliances"]["blue"]["team1"]]['allianceScore'] += adjBlueScore/(2.*teams[match["alliances"]["blue"]["team1"]]['real_matches'])
            teams[match["alliances"]["blue"]["team2"]]['allianceScore'] += adjBlueScore/(2.*teams[match["alliances"]["blue"]["team2"]]['real_matches'])
            teams[match["alliances"]["red"]["team1"]]['allianceScore'] += adjRedScore/(2.*teams[match["alliances"]["red"]["team1"]]['real_matches'])
            teams[match["alliances"]["red"]["team2"]]['allianceScore'] += adjRedScore/(2.*teams[match["alliances"]["red"]["team2"]]['real_matches'])

        # OK... now on to powerScores
        for matchid in matches:
            match = matches[matchid]

            adjBlueScore = match["alliances"]["blue"]["total"]-match["alliances"]["blue"]["pen"]
            adjRedScore = match["alliances"]["red"]["total"]-match["alliances"]["red"]["pen"]

            # Now, split up the scores, not on a 50-50 split like we did the first time, but based on the alliance scores for each team that we just calculated
            # Again, we're doing the division by the number of matches to normalize to the number of matches played
            if (teams[match["alliances"]["blue"]["team1"]]['allianceScore'] + teams[match["alliances"]["blue"]["team2"]]['allianceScore']) >0:
                teams[match["alliances"]["blue"]["team1"]]['powerScore'] += adjBlueScore * teams[match["alliances"]["blue"]["team1"]]['allianceScore']/ ((teams[match["alliances"]["blue"]["team1"]]['allianceScore'] + teams[match["alliances"]["blue"]["team2"]]['allianceScore'])* teams[match["alliances"]["blue"]["team1"]]['real_matches'])
                teams[match["alliances"]["blue"]["team2"]]['powerScore'] += adjBlueScore * teams[match["alliances"]["blue"]["team2"]]['allianceScore']/ ((teams[match["alliances"]["blue"]["team1"]]['allianceScore'] + teams[match["alliances"]["blue"]["team2"]]['allianceScore'])* teams[match["alliances"]["blue"]["team2"]]['real_matches'])
            if (teams[match["alliances"]["red"]["team1"]]['allianceScore'] + teams[match["alliances"]["red"]["team2"]]['allianceScore']) >0:
                teams[match["alliances"]["red"]["team1"]]['powerScore'] += adjRedScore * teams[match["alliances"]["red"]["team1"]]['allianceScore']/ ((teams[match["alliances"]["red"]["team1"]]['allianceScore'] + teams[match["alliances"]["red"]["team2"]]['allianceScore'])* teams[match["alliances"]["red"]["team1"]]['real_matches'])
                teams[match["alliances"]["red"]["team2"]]['powerScore'] += adjRedScore * teams[match["alliances"]["red"]["team2"]]['allianceScore']/ ((teams[match["alliances"]["red"]["team1"]]['allianceScore'] + teams[match["alliances"]["red"]["team2"]]['allianceScore'])* teams[match["alliances"]["red"]["team2"]]['real_matches'])





    #except:
    #    print("ERROR: Initial contact of the scoring system failed.")
    #    print()
    #    exit()

    
    
def create_skill():
    return AstromechPit()
