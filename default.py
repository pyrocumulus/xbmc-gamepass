# -*- coding: utf-8 -*-
"""
A Kodi addon/skin for NFL Game Pass
"""
import sys
import json
from traceback import format_exc
from datetime import timedelta
import logging

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from resources.lib.pigskin.pigskin import pigskin
from resources.lib import kodiutils
from resources.lib import kodilogging

addon = xbmcaddon.Addon()
language = addon.getLocalizedString
ADDON_PATH = xbmc.translatePath(addon.getAddonInfo('path'))
ADDON_PROFILE = xbmc.translatePath(addon.getAddonInfo('profile'))

logger = logging.getLogger(addon.getAddonInfo('id'))
kodilogging.config()

busydialog = xbmcgui.DialogBusy()

if not xbmcvfs.exists(ADDON_PROFILE):
    xbmcvfs.mkdir(ADDON_PROFILE)

username = addon.getSetting('email')
password = addon.getSetting('password')

proxy_url = None
if addon.getSetting('proxy_enabled') == 'true':
    proxy_url = build_proxy_url(self)

gp = pigskin(proxy_url=proxy_url)


def show_busy_dialog():
    busydialog.create()


def hide_busy_dialog():
    try:
        busydialog.close()
    except RuntimeError as e:
        logger.error('Error closing busy dialog: %s' % e.message)


class GamepassGUI(xbmcgui.WindowXML):
    def __init__(self, *args, **kwargs):
        self.season_list = None
        self.season_items = []
        self.clicked_season = -1
        self.weeks_list = None
        self.weeks_items = []
        self.clicked_week = -1
        self.games_list = None
        self.games_items = []
        self.clicked_game = -1
        self.live_list = None
        self.live_items = []
        self.selected_season = ''
        self.selected_week = ''
        self.main_selection = None
        self.player = None
        self.list_refill = False
        self.focusId = 100
        self.seasons_and_weeks = gp.get_seasons_and_weeks()
        self.has_inputstream_adaptive = self.has_inputstream_adaptive()

        xbmcgui.WindowXML.__init__(self, *args, **kwargs)
        self.action_previous_menu = (9, 10, 92, 216, 247, 257, 275, 61467, 61448)

    def onInit(self):  # pylint: disable=invalid-name
        self.window = xbmcgui.Window(xbmcgui.getCurrentWindowId())
        self.season_list = self.window.getControl(210)
        self.weeks_list = self.window.getControl(220)
        self.games_list = self.window.getControl(230)
        self.live_list = self.window.getControl(240)

        if self.list_refill:
            self.season_list.reset()
            self.season_list.addItems(self.season_items)
            self.weeks_list.reset()
            self.weeks_list.addItems(self.weeks_items)
            self.games_list.reset()
            self.games_list.addItems(self.games_items)
            self.live_list.reset()
            self.live_list.addItems(self.live_items)
        else:
            self.window.setProperty('NW_clicked', 'false')
            self.window.setProperty('GP_clicked', 'false')

        hide_busy_dialog()

        try:
            self.setFocus(self.window.getControl(self.focusId))
        except:
            logger.error('Focus not possible: %s' % self.focusId)

    def build_proxy_url(self):
        proxy_url = ''
        protocol = addon.getSetting('proxy_scheme') + '://'

        auth = ''
        if addon.getSetting('proxy_auth') == 'true':
            username = addon.getSetting('proxy_username').strip()
            password = addon.getSetting('proxy_password')

            if not username or not password:
                return ''

            auth = '%s:%s@' % (urllib.quote(username), urllib.quote(password))

        host = addon.getSetting('proxy_host').strip()
        if not host:
            return ''

        port = addon.getSetting('proxy_port').strip()
        if port:
            host = host + ':' + port

        proxy_url = protocol + auth + host

        return proxy_url

    def coloring(self, text, meaning):
        """Return the text wrapped in appropriate color markup."""
        if meaning == "disabled":
            color = "FF000000"
        elif meaning == "disabled-info":
            color = "FF111111"
        colored_text = "[COLOR=%s]%s[/COLOR]" % (color, text)
        return colored_text

    def display_seasons(self):
        """List seasons"""
        self.season_items = []
        for season in sorted(self.seasons_and_weeks.keys(), reverse=True):
            listitem = xbmcgui.ListItem(season)
            self.season_items.append(listitem)

        self.season_list.addItems(self.season_items)

    def display_nfln_seasons(self):
        """List seasons"""
        self.season_items = []
        self.seasons = set([year for show in gp.nfln_shows for year in gp.nfln_shows[show]])
        for season in sorted(self.seasons, reverse=True):
            listitem = xbmcgui.ListItem(season)
            self.season_items.append(listitem)

        self.season_list.addItems(self.season_items)

    def display_nfl_network_archive(self):
        """List shows for a given season"""
        self.weeks_items = []
        shows = gp.get_shows(self.selected_season)
        for show_name in shows:
            listitem = xbmcgui.ListItem(show_name)
            self.weeks_items.append(listitem)

        self.weeks_list.addItems(self.weeks_items)

    def display_weeks_games(self):
        """Show games for a given season/week"""
        self.games_items = []
        games = gp.get_weeks_games(self.selected_season, self.selected_season_type, self.selected_week)
        for game in games:
            game_id = '{0}-{1}-{2}'.format(game['visitorNickName'].lower(), game['homeNickName'].lower(), str(game['gameId']))
            game_name_shrt = '[B]%s[/B] at [B]%s[/B]' % (game['visitorNickName'], game['homeNickName'])
            game_name_full = '[B]%s %s[/B] at [B]%s %s[/B]' % (game['visitorCityState'], game['visitorNickName'], game['homeCityState'], game['homeNickName'])
            listitem = xbmcgui.ListItem(game_name_shrt, game_name_full)

            listitem.setProperty('is_game', 'true')
            listitem.setProperty('is_show', 'false')

            if game['phase'] == 'FINAL' or game['phase'] == 'FINAL_OVERTIME':
                # show game duration only if user wants to see it
                if addon.getSetting('hide_game_length') == 'false' and game['video']:
                    if game['video']['videoDuration'] == '':
                        game['video']['videoDuration'] = '0'
                    game_info = '%s [CR] Duration: %s' % (game['phase'], str(timedelta(seconds=int(float(game['video']['videoDuration'].replace(',', '.'))))))
                else:
                    game_info = game['phase']
                    if addon.getSetting('hide_game_length') == 'true' and game_info == 'FINAL_OVERTIME':
                        game_info = 'FINAL'
            else:
                if addon.getSetting('time_notation') == '0':  # 12-hour clock
                    datetime_format = '%A, %b %d - %I:%M %p'
                else:  # 24-hour clock
                    datetime_format = '%A, %b %d - %H:%M'

                datetime_obj = gp.parse_datetime(game['gameDateTimeUtc'], True)
                game_info = datetime_obj.strftime(datetime_format).encode('utf-8')

            if game['videoStatus'] == 'SCHEDULED':
                isPlayable = 'false'
                isBlackedOut = 'false'
            elif game['videoStatus'] == 'LIVE':
                game_info += '[CR]» Live «'
                video_id = str(game['video']['videoId'])
                isPlayable = 'true'
                isBlackedOut = 'false'
                listitem.setProperty('live_video_id', video_id)
            else:  # ONDEMAND
                isPlayable = 'true'
                isBlackedOut = 'false'

            listitem.setProperty('isPlayable', isPlayable)
            listitem.setProperty('isBlackedOut', isBlackedOut)
            listitem.setProperty('game_id', game_id)
            listitem.setProperty('game_info', game_info)
            listitem.setProperty('away_thumb', 'http://i.nflcdn.com/static/site/7.4/img/logos/teams-matte-144x96/%s.png' % game['visitorTeamAbbr'])
            listitem.setProperty('home_thumb', 'http://i.nflcdn.com/static/site/7.4/img/logos/teams-matte-144x96/%s.png' % game['homeTeamAbbr'])
            self.games_items.append(listitem)
        self.games_list.addItems(self.games_items)

    def display_seasons_weeks(self):
        """List weeks for a given season"""
        weeks_dict = self.seasons_and_weeks[self.selected_season]

        for week in weeks_dict:
            if week['week_name'] == 'p':
                title = language(30047).format(week['week_number'])
            elif week['week_name'] == 'week':
                title = language(30048).format(week['week_number'])
            else:
                title = week['week_name'].upper()
            future = 'false'
            listitem = xbmcgui.ListItem(title)
            listitem.setProperty('week', week['week_number'])
            listitem.setProperty('season_type', week['season_type'])
            listitem.setProperty('future', future)
            self.weeks_items.append(listitem)
        self.weeks_list.addItems(self.weeks_items)

    def display_shows_episodes(self, show_name, season):
        """Show episodes for a given season/show"""
        self.games_items = []
        episodes = gp.get_shows_episodes(show_name, season)

        for episode in episodes:
            try:
                listitem = xbmcgui.ListItem('[B]%s[/B]' % show_name)
                for episode_title, episode_videoId_thumbnail in episode.items():
                    listitem.setProperty('game_info', episode_title)
                    for episode_videoId, episode_thumbnail in episode_videoId_thumbnail.items():
                        listitem.setProperty('id', episode_videoId)
                        listitem.setProperty('away_thumb', episode_thumbnail.replace('{formatInstructions}', 'c_thumb,q_auto,f_png'))
                listitem.setProperty('is_game', 'false')
                listitem.setProperty('is_show', 'true')
                listitem.setProperty('isPlayable', 'true')
                self.games_items.append(listitem)
            except:
                logger.error('Exception adding archive directory: %s' % format_exc())
                logger.error('Directory name: %s' % episode_title)
        self.games_list.addItems(self.games_items)

    def play_url(self, url):
        hide_busy_dialog()
        self.list_refill = True
        playitem = xbmcgui.ListItem(path=url)
        if self.has_inputstream_adaptive and addon.getSetting('use_inputstream_adaptive') == 'true':
            playitem.setProperty('inputstreamaddon', 'inputstream.adaptive')
            playitem.setProperty('inputstream.adaptive.manifest_type', 'hls')
            playitem.setProperty('inputstream.adaptive.stream_headers', url.split('|')[1])
        xbmc.Player().play(item=url, listitem=playitem)

    def init(self, level):
        if level == 'season':
            self.weeks_items = []
            self.weeks_list.reset()
            self.games_list.reset()
            self.clicked_week = -1
            self.clicked_game = -1

            if self.clicked_season > -1:  # unset previously selected season
                self.season_list.getListItem(self.clicked_season).setProperty('clicked', 'false')

            self.season_list.getSelectedItem().setProperty('clicked', 'true')
            self.clicked_season = self.season_list.getSelectedPosition()
        elif level in {'week', 'show'}:
            self.games_list.reset()
            self.clicked_game = -1

            if self.clicked_week > -1:  # unset previously selected week/show
                self.weeks_list.getListItem(self.clicked_week).setProperty('clicked', 'false')

            self.weeks_list.getSelectedItem().setProperty('clicked', 'true')
            self.clicked_week = self.weeks_list.getSelectedPosition()
        elif level in {'game', 'episode'}:
            if self.clicked_game > -1:  # unset previously selected game/episode
                self.games_list.getListItem(self.clicked_game).setProperty('clicked', 'false')

            self.games_list.getSelectedItem().setProperty('clicked', 'true')
            self.clicked_game = self.games_list.getSelectedPosition()

    def ask_bitrate(self, bitrates):
        """Presents a dialog for user to select from a list of bitrates.
        Returns the value of the selected bitrate.
        """
        options = []
        for bitrate in bitrates:
            options.append(str(bitrate) + ' Kbps')
        dialog = xbmcgui.Dialog()
        hide_busy_dialog()
        ret = dialog.select(language(30003), options)
        if ret > -1:
            return bitrates[ret]
        else:
            return None

    def select_bitrate(self, manifest_bitrates=None):
        """Returns a bitrate, while honoring the user's /preference/."""
        bitrate_setting = int(addon.getSetting('preferred_bitrate'))
        bitrate_values = ['3671533', '2394274', '1577316', '1117771', '760027', '555799', '402512']

        highest = False
        preferred_bitrate = None
        if bitrate_setting == 0:  # 0 === "highest"
            highest = True
        elif 0 < bitrate_setting and bitrate_setting < 8:  # a specific bitrate. '8' === "ask"
            preferred_bitrate = bitrate_values[bitrate_setting - 1]

        if manifest_bitrates:
            manifest_bitrates.sort(key=int, reverse=True)
            if highest:
                return manifest_bitrates[0]
            elif preferred_bitrate and preferred_bitrate in manifest_bitrates:
                return preferred_bitrate
            else:  # ask user
                return self.ask_bitrate(manifest_bitrates)
        else:
            if highest:
                return bitrate_values[0]
            elif preferred_bitrate:
                return preferred_bitrate
            else:  # ask user
                return self.ask_bitrate(bitrate_values)

    def select_version(self, game_versions):
        """Selects a game version and returns the video ID while honoring the user's /preference/."""
        preferred_version = int(addon.getSetting('preferred_game_version'))
        if preferred_version == 0:
            selected_version = 'Game video'
        elif preferred_version == 1:
            selected_version = 'Condensed game'
        elif preferred_version == 2:
            selected_version = 'Coach film'
        else:
            selected_version = None

        # user wants to be asked to select version
        # bring up selection when preferred game version is unavailable
        if not selected_version or selected_version not in game_versions:
            versions = game_versions.keys()
            dialog = xbmcgui.Dialog()
            hide_busy_dialog()
            answer = dialog.select(language(30016), versions)
            if answer > -1:
                selected_version = versions[answer]
                logger.debug('Selected version: %s' % selected_version)
            else:
                logger.debug('Select version dialog was cancelled.')
                return None

        return game_versions[selected_version]

    def has_inputstream_adaptive(self):
        """Checks if InputStream Adaptive is installed and enabled."""
        payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'Addons.GetAddonDetails',
            'params': {
                'addonid': 'inputstream.adaptive',
                'properties': ['enabled']
            }
        }
        response = xbmc.executeJSONRPC(json.dumps(payload))
        data = json.loads(response)
        if 'error' not in data and data['result']['addon']['enabled']:
            logger.debug('InputStream Adaptive is installed and enabled.')
            return True
        else:
            logger.debug('InputStream Adaptive is not installed and/or enabled.')
            if addon.getSetting('use_inputstream_adaptive') == 'true':
                logger.info('Disabling InputStream Adaptive.')
                addon.setSetting('use_inputstream_adaptive', 'false')  # reset setting
            return False

    def select_stream_url(self, streams):
        """Determine which stream URL to use."""
        if not streams:
            logger.warning('no streams list was provided!')
            dialog = xbmcgui.Dialog()
            dialog.ok(language(30043), language(30045))
            return False

        # prefer chromecast streams (as they're of higher quality) but fallback
        # to HLS when they're not present
        try:
            url = streams['chromecast']
        except KeyError:
            url = streams['hls']

        if addon.getSetting('use_inputstream_adaptive') == 'true' and self.has_inputstream_adaptive:
            return url
        else:  # choose a specific bitrate
            try:
                m3u8_streams = gp.m3u8_to_dict(url)
                bitrate = self.select_bitrate(m3u8_streams.keys())
                if bitrate:
                    return m3u8_streams[bitrate]
                else:  # bitrate dialog was canceled
                    return None
            except:
                logger.error('unable to parse the m3u8 manifest.')
                dialog = xbmcgui.Dialog()
                dialog.ok(language(30043), language(30045))
                return False

    def onFocus(self, controlId):  # pylint: disable=invalid-name
        # save currently focused list
        if controlId in [210, 220, 230, 240]:
            self.focusId = controlId

    def onClick(self, controlId):  # pylint: disable=invalid-name
        try:
            show_busy_dialog()
            if controlId in [110, 120, 130]:
                self.games_list.reset()
                self.weeks_list.reset()
                self.season_list.reset()
                self.live_list.reset()
                self.games_items = []
                self.weeks_items = []
                self.live_items = []
                self.clicked_game = -1
                self.clicked_week = -1
                self.clicked_season = -1

                if controlId in [110, 120]:
                    self.main_selection = 'GamePass'
                    self.window.setProperty('NW_clicked', 'false')
                    self.window.setProperty('GP_clicked', 'true')

                    # display games of current week for usability purposes
                    cur_s_w = gp.get_current_season_and_week()
                    self.selected_season = cur_s_w['season']
                    self.selected_season_type = cur_s_w['season_type']
                    self.selected_week = cur_s_w['week']
                    self.display_seasons()

                    try:
                        self.display_seasons_weeks()
                        self.display_weeks_games()
                    except:
                        logger.error('Error while reading seasons weeks and games')
                elif controlId == 130:
                    self.main_selection = 'NFL Network'
                    self.window.setProperty('NW_clicked', 'true')
                    self.window.setProperty('GP_clicked', 'false')
                    gp.parse_shows()

                    listitem = xbmcgui.ListItem('NFL Network - Live', 'NFL Network - Live')
                    self.live_items.append(listitem)

                    if gp.redzone_on_air():
                        listitem = xbmcgui.ListItem('NFL RedZone - Live', 'NFL RedZone - Live')
                        self.live_items.append(listitem)

                    self.live_list.addItems(self.live_items)
                    self.display_nfln_seasons()

                hide_busy_dialog()
                return

            if self.main_selection == 'GamePass':
                if controlId == 210:  # season is clicked
                    self.init('season')
                    self.selected_season = self.season_list.getSelectedItem().getLabel()

                    self.display_seasons_weeks()
                elif controlId == 220:  # week is clicked
                    self.init('week')
                    self.selected_week = self.weeks_list.getSelectedItem().getProperty('week')
                    self.selected_season_type = self.weeks_list.getSelectedItem().getProperty('season_type')

                    self.display_weeks_games()
                elif controlId == 230:  # game is clicked
                    selected_game = self.games_list.getSelectedItem()
                    if selected_game.getProperty('isPlayable') == 'true':
                        self.init('game')
                        game_id = selected_game.getProperty('game_id')

                        if selected_game.getProperty('live_video_id'):
                            video_id = selected_game.getProperty('live_video_id')
                        else:
                            game_versions = gp.get_game_versions(game_id, self.selected_season)
                            video_id = self.select_version(game_versions)

                        if video_id:
                            streams = gp.get_streams(video_id, 'game', username=username)
                            stream_url = self.select_stream_url(streams)
                            self.play_url(stream_url)

            elif self.main_selection == 'NFL Network':
                if controlId == 210:  # season is clicked
                    self.init('season')
                    self.selected_season = self.season_list.getSelectedItem().getLabel()

                    self.display_nfl_network_archive()
                elif controlId == 220:  # show is clicked
                    self.init('show')
                    show_name = self.weeks_list.getSelectedItem().getLabel()

                    self.display_shows_episodes(show_name, self.selected_season)
                elif controlId == 230:  # episode is clicked
                    self.init('episode')
                    video_id = self.games_list.getSelectedItem().getProperty('id')
                    streams = gp.get_streams(video_id, 'video', username=username)
                    stream_url = self.select_stream_url(streams)

                    self.play_url(stream_url)
                elif controlId == 240:  # Live content (though not games)
                    show_name = self.live_list.getSelectedItem().getLabel()
                    if show_name == 'NFL RedZone - Live':
                        streams = gp.get_streams('redzone', username=username)
                        stream_url = self.select_stream_url(streams)

                        self.play_url(stream_url)
                    elif show_name == 'NFL Network - Live':
                        streams = gp.get_streams('nfl_network', username=username)
                        stream_url = self.select_stream_url(streams)

                        self.play_url(stream_url)
            hide_busy_dialog()
        except Exception:  # catch anything that might fail
            hide_busy_dialog()
            logger.error(format_exc())

            dialog = xbmcgui.Dialog()
            if self.main_selection == 'NFL Network' and controlId == 230:  # episode
                # inform that not all shows will work
                dialog.ok(language(30043), language(30044))
            else:
                # generic oops
                dialog.ok(language(30021), language(30024))


class CoachesFilmGUI(xbmcgui.WindowXML):
    def __init__(self, xmlFilename, scriptPath, plays, defaultSkin='Default', defaultRes='720p'):  # pylint: disable=invalid-name
        self.playsList = None
        self.playsItems = plays

        xbmcgui.WindowXML.__init__(self, xmlFilename, scriptPath, defaultSkin, defaultRes)
        self.action_previous_menu = (9, 10, 92, 216, 247, 257, 275, 61467, 61448)

    def onInit(self):  # pylint: disable=invalid-name
        self.window = xbmcgui.Window(xbmcgui.getCurrentWindowId())
        if addon.getSetting('coach_lite') == 'true':
            self.window.setProperty('coach_lite', 'true')

        self.playsList = self.window.getControl(110)
        self.window.getControl(99).setLabel(language(30032))
        self.playsList.addItems(self.playsItems)
        self.setFocus(self.playsList)
        url = self.playsList.getListItem(0).getProperty('url')
        hide_busy_dialog()
        xbmc.executebuiltin('PlayMedia(%s,False,1)' % url)

    def onClick(self, controlId):  # pylint: disable=invalid-name
        if controlId == 110:
            url = self.playsList.getSelectedItem().getProperty('url')
            xbmc.executebuiltin('PlayMedia(%s,False,1)' % url)


if __name__ == '__main__':
    logger.debug('script starting')
    hide_busy_dialog()

    if not username or not password:
        dialog = xbmcgui.Dialog()
        answer = dialog.ok(language(30021), language(30050))

        if answer:
            addon.openSettings()
            username = addon.getSetting('email')
            password = addon.getSetting('password')
        else:
            sys.exit(0)

    try:
        gp.login(username, password)
    except gp.GamePassError as error:
        dialog = xbmcgui.Dialog()
        if error.value == 'error_unauthorised' or error.value == 'no_subscription':
            dialog.ok(language(30021), language(30023))
        else:
            dialog.ok(language(30021), error.value)
        sys.exit(0)
    except:
        logger.error(format_exc())
        dialog = xbmcgui.Dialog()
        dialog.ok('Epic Failure',
                  language(30024))
        sys.exit(0)

    gui = GamepassGUI('script-gamepass.xml', ADDON_PATH)
    gui.doModal()
    del gui

logger.debug('script finished')
