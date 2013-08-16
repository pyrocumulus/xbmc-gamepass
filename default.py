﻿import urllib
import urllib2
import re
import os
import json
import cookielib
import xbmcplugin
import xbmcgui
import xbmcvfs
import xbmcaddon
import StorageServer
from traceback import format_exc
from urlparse import urlparse, parse_qs
from BeautifulSoup import BeautifulSoup
from BeautifulSoup import BeautifulStoneSoup

addon = xbmcaddon.Addon(id='plugin.video.nfl.gamepass')
addon_path = xbmc.translatePath(addon.getAddonInfo('path'))
addon_profile = xbmc.translatePath(addon.getAddonInfo('profile'))
cookie_file = os.path.join(addon_profile, 'cookie_file')
cookie_jar = cookielib.LWPCookieJar(cookie_file)
icon = os.path.join(addon_path, 'icon.png')
fanart = os.path.join(addon_path, 'fanart.jpg')
base_url = ''
debug = addon.getSetting('debug')
addon_version = addon.getAddonInfo('version')
cache = StorageServer.StorageServer("nfl_game_pass", 24)
username = addon.getSetting('email')
password = addon.getSetting('password')


def addon_log(string):
    if debug == 'true':
        xbmc.log("[addon.nfl.gamepass-%s]: %s" %(addon_version, string))

def cache_seasons_and_weeks(login_data):
    soup = BeautifulSoup(login_data, convertEntities=BeautifulSoup.HTML_ENTITIES)

    try:
        seasons_soup = soup.find('select', id='seasonSelect').findChildren()
        seasons = []
        for season in seasons_soup:
            seasons.append(season.string)
        cache.set('seasons', repr(seasons))
        addon_log('Seasons cached')
    except:
        addon_log('Season cache failed')
        return False

    try:
        weeks_soup = soup.find('select', id='weekSelect').findChildren()
        weeks = {}
        for week in weeks_soup:
            week_code = week['value']
            weeks[week_code] = week.string
        cache.set('weeks', repr(weeks))
        addon_log('Weeks cached')
    except:
        addon_log('Week cache failed')
        return False

    return True

def display_games(season, week_code):
    games = get_weeks_games(season, week_code)
    if games:
        for game_id, game_name in games.iteritems():
            add_dir(game_name, game_id, 4, icon)
    else:
        dialog = xbmcgui.Dialog()
        dialog.ok("Fetching Games Failed", "Fetching Game Data Failed.")
        addon_log('Fetching games failed.')

def display_seasons(seasons):
    for season in seasons:
        add_dir(season, season, 2, icon)

def display_weeks(season, weeks):
    for week_code, week_name in sorted(weeks.iteritems()):
        add_dir(week_name, season + ';' + week_code, 3, icon)

# logs in and returns a list of available seasons
def gamepass_login():
    url = 'https://id.s.nfl.com/login'
    post_data = {
        'username': username,
        'password': password,
        'vendor_id': 'nflptnrnln',
        'error_url': 'https://gamepass.nfl.com/nflgp/secure/login?redirect=loginform&redirectnosub=packages&redirectsub=schedule',
        'success_url': 'https://gamepass.nfl.com/nflgp/secure/login?redirect=loginform&redirectnosub=packages&redirectsub=schedule'
    }
    login_data = make_request(url, urllib.urlencode(post_data))

    cache_success = cache_seasons_and_weeks(login_data)

    if cache_success:
        addon_log('login success')
    else: # if cache failed, then login failed or the login page's HTML changed
        dialog = xbmcgui.Dialog()
        dialog.ok("Login Failed", "Logging into NFL GamePass failed. Make sure your account information is correct.")
        addon_log('login failed')

# season is in format: YYYY
# week is in format 101 (1st week preseason) or 213 (13th week of regular season)
def get_weeks_games(season, week):
    url = 'https://gamepass.nfl.com/nflgp/servlets/games'
    post_data = {
        'isFlex': 'true',
        'season': season,
        'week': week
    }
    games = {}
    game_data = make_request(url, urllib.urlencode(post_data))

    soup = BeautifulStoneSoup(game_data, convertEntities=BeautifulSoup.XML_ENTITIES)
    games_soup = soup.find('games').findChildren()
    for game in games_soup:
        game_id = ''
        try:
            game_id = game.programid.string
            games[game_id] = ''
        except AttributeError:
            addon_log('No program id: %s' %game)
            # the first item doen't seem to be a game, so continue to the next item
            continue

        away_team = game.awayteam('city')[0].string + ' ' + game.awayteam('name')[0].string
        home_team = game.hometeam('city')[0].string + ' ' + game.hometeam('name')[0].string
        games[game_id] = away_team + ' at ' + home_team

    return games

def make_request(url, data=None, headers=None):
    addon_log('Request URL: %s' %url)
    if headers is None:
        headers = {'User-agent' : 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:22.0) Gecko/20100101 Firefox/22.0',
                   'Referer' : base_url}
    if not xbmcvfs.exists(cookie_file):
        addon_log('Creating cookie_file!')
        cookie_jar.save()
    cookie_jar.load(cookie_file, ignore_discard=True, ignore_expires=True)
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookie_jar))
    urllib2.install_opener(opener)
    try:
        req = urllib2.Request(url, data, headers)
        response = urllib2.urlopen(req)
        cookie_jar.save(cookie_file, ignore_discard=True, ignore_expires=False)
        data = response.read()
        addon_log(str(response.info()))
        redirect_url = response.geturl()
        response.close()
        if redirect_url != url:
                addon_log('Redirect URL: %s' %redirect_url)
        return data
    except urllib2.URLError, e:
        addon_log('We failed to open "%s".' %url)
        if hasattr(e, 'reason'):
            addon_log('We failed to reach a server.')
            addon_log('Reason: ', e.reason)
        if hasattr(e, 'code'):
            addon_log('We failed with error code - %s.' %e.code)

def add_dir(name, url, mode, iconimage):
    params = {'name': name, 'url': url, 'mode': mode}
    url = '%s?%s' %(sys.argv[0], urllib.urlencode(params))
    listitem = xbmcgui.ListItem(name, iconImage=iconimage, thumbnailImage=iconimage)
    listitem.setProperty("Fanart_Image", fanart)
    xbmcplugin.addDirectoryItem(int(sys.argv[1]), url, listitem, True)

def get_params():
    p = parse_qs(sys.argv[2][1:])
    for i in p.keys():
        p[i] = p[i][0]
    return p


if debug == 'true':
    cache.dbg = True
params = get_params()
addon_log("params: %s" %params)

try:
    mode = int(params['mode'])
except:
    mode = None

if mode == None:
    add_dir('Login', 'login', 1, icon)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 1:
    gamepass_login()
    seasons = eval(cache.get('seasons'))
    display_seasons(seasons)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 2:
    weeks = eval(cache.get('weeks'))
    season = params['name']
    display_weeks(season, weeks)
    # add_plugin dir
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 3:
    season, week_code = params['url'].split(';', 1)
    display_games(season, week_code)
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

elif mode == 4:
    xbmcplugin.endOfDirectory(int(sys.argv[1]))
