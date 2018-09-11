from base64 import b32decode, b16encode
import random
import re

from wakeonlan import send_magic_packet

from couchpotato.api import addApiView
from couchpotato.core.event import addEvent
from couchpotato.core.helpers.variable import mergeDicts
from couchpotato.core.logger import CPLog
from couchpotato.core.media._base.providers.base import Provider
from couchpotato.core.plugins.base import Plugin


log = CPLog(__name__)


## This is here to load the static files
class Downloader(Plugin):
    pass


class DownloaderBase(Provider):

    protocol = []
    http_time_between_calls = 0
    status_support = True

    torrent_sources = [
        'https://torcache.net/torrent/%s.torrent',
        'https://itorrents.org/torrent/%s.torrent',
    ]

    torrent_trackers = [
        'udp://tracker.istole.it:80/announce',
        'http://tracker.istole.it/announce',
        'udp://fr33domtracker.h33t.com:3310/announce',
        'http://tracker.publicbt.com/announce',
        'udp://tracker.publicbt.com:80/announce',
        'http://tracker.ccc.de/announce',
        'udp://tracker.ccc.de:80/announce',
        'http://exodus.desync.com/announce',
        'http://exodus.desync.com:6969/announce',
        'http://tracker.publichd.eu/announce',
        'udp://tracker.publichd.eu:80/announce',
        'http://tracker.openbittorrent.com/announce',
        'udp://tracker.openbittorrent.com/announce',
        'udp://tracker.openbittorrent.com:80/announce',
        'udp://open.demonii.com:1337/announce',
    ]

    def __init__(self):
        addEvent('download', self._download)
        addEvent('download.enabled', self._isEnabled)
        addEvent('download.enabled_protocols', self.getEnabledProtocol)
        addEvent('download.status', self._getAllDownloadStatus)
        addEvent('download.remove_failed', self._removeFailed)
        addEvent('download.pause', self._pause)
        addEvent('download.process_complete', self._processComplete)
        addApiView('download.%s.test' % self.getName().lower(), self._test)

    def getEnabledProtocol(self):
        for download_protocol in self.protocol:
            if self.isEnabled(manual = True, data = {'protocol': download_protocol}):
                return self.protocol

        return []

    def _is_downloader_awake(self, timeout = True):

        wake_enabled = self.conf('wake_enabled', default = False, section = 'download_basics')
        wait_enabled = self.conf('wait_enabled', default = False, section = 'download_basics')

        if wake_enabled and wait_enabled:

            service_ip      = self.conf('ip_address', section = 'download_basics')
            service_port    = int(self.conf('port', default = 8080, section = 'download_basics'))
            service_timeout = int(self.conf('timeout', default = 1, section = 'download_basics'))

            if not timeout:
                service_timeout = 1

            log.debug('Checking if service is available @{}:{}.'.format(service_ip, service_port))
            online = self.wait_net_service(service_ip, service_port, service_timeout)
            log.info('Service {}:{} available? {}'.format(service_ip, service_port, online))
            return online
        
        log.debug('Skipping service availability check.')
        return True
        
    def _wake(self):
        mac_address = self.conf('mac_address', section = 'download_basics')
        log.debug('Waking machine before download with mac address "{}"'.format(mac_address))
        send_magic_packet(mac_address)

        if not self._is_downloader_awake():
            log.warning('Wake on download failed.')


    def _download(self, data = None, media = None, manual = False, filedata = None):
        if not media: media = {}
        if not data: data = {}

        if self.isDisabled(manual, data):
            return

        if not self._is_downloader_awake(timeout = False):
            self._wake()
        
        return self.download(data = data, media = media, filedata = filedata)

    def download(self, *args, **kwargs):
        return False

    def _getAllDownloadStatus(self, download_ids):
        if self.isDisabled(manual = True, data = {}):
            return

        ids = [download_id['id'] for download_id in download_ids if download_id['downloader'] == self.getName()]

        if ids:    
            if not self._is_downloader_awake(False):
                self._wake()

            return self.getAllDownloadStatus(ids)
        else:
            return

    def getAllDownloadStatus(self, ids):
        return []

    def _removeFailed(self, release_download):
        if self.isDisabled(manual = True, data = {}):
            return

        if release_download and release_download.get('downloader') == self.getName():
            if self.conf('delete_failed'):
                return self.removeFailed(release_download)

            return False
        return

    def removeFailed(self, release_download):
        return

    def _processComplete(self, release_download):
        if self.isDisabled(manual = True, data = {}):
            return

        if release_download and release_download.get('downloader') == self.getName():
            if self.conf('remove_complete', default = False):
                return self.processComplete(release_download = release_download, delete_files = self.conf('delete_files', default = False))

            return False
        return

    def processComplete(self, release_download, delete_files):
        return

    def isCorrectProtocol(self, protocol):
        is_correct = protocol in self.protocol

        if not is_correct:
            log.debug("Downloader doesn't support this protocol")

        return is_correct

    def magnetToTorrent(self, magnet_link):
        torrent_hash = re.findall('urn:btih:([\w]{32,40})', magnet_link)[0].upper()

        # Convert base 32 to hex
        if len(torrent_hash) == 32:
            torrent_hash = b16encode(b32decode(torrent_hash))

        sources = self.torrent_sources
        random.shuffle(sources)

        for source in sources:
            try:
                filedata = self.urlopen(source % torrent_hash, headers = {'Referer': source % torrent_hash}, show_error = False)
                if 'torcache' in filedata and 'file not found' in filedata.lower():
                    continue

                return filedata
            except:
                log.debug('Torrent hash "%s" wasn\'t found on: %s', (torrent_hash, source))

        log.error('Failed converting magnet url to torrent: %s', torrent_hash)
        return False

    def downloadReturnId(self, download_id):
        return {
            'downloader': self.getName(),
            'status_support': self.status_support,
            'id': download_id
        }

    def isDisabled(self, manual = False, data = None):
        if not data: data = {}

        return not self.isEnabled(manual, data)

    def _isEnabled(self, manual, data = None):
        if not data: data = {}

        if not self.isEnabled(manual, data):
            return
        return True

    def isEnabled(self, manual = False, data = None):
        if not data: data = {}

        d_manual = self.conf('manual', default = False)
        return super(DownloaderBase, self).isEnabled() and \
            (d_manual and manual or d_manual is False) and \
            (not data or self.isCorrectProtocol(data.get('protocol')))

    def _test(self, **kwargs):
        t = self.test()
        if isinstance(t, tuple):
            return {'success': t[0], 'msg': t[1]}
        return {'success': t}

    def test(self):
        
        if not self._is_downloader_awake(False):
            self._wake()

        return False

    def _pause(self, release_download, pause = True):
        if self.isDisabled(manual = True, data = {}):
            return

        if release_download and release_download.get('downloader') == self.getName():
            self.pause(release_download, pause)
            return True

        return False

    def pause(self, release_download, pause):
        return

    def wait_net_service(self, server, port, timeout=None):
        """ Wait for network service to appear 
            @param timeout: in seconds, if None or 0 wait forever
            @return: True of False, if timeout is None may return only True or
                     throw unhandled network exception
        """
        import socket
        import errno

        s = socket.socket()
        if timeout:
            from time import time as now
            # time module is needed to calc timeout shared between two exceptions
            end = now() + timeout

        while True:
            try:
                if timeout:
                    next_timeout = end - now()
                    if next_timeout < 0:
                        return False
                    else:
                        s.settimeout(next_timeout)
            
                s.connect((server, port))
        
            except socket.timeout, err:
                # this exception occurs only if timeout is set
                if timeout:
                    return False
      
            except socket.error, err:
                # catch timeout exception from underlying network library
                # this one is different from socket.timeout
                if type(err.args) != tuple or err[0] != errno.ETIMEDOUT:
                    log.error(err)
                    raise
            else:
                s.close()
                return True

class ReleaseDownloadList(list):

    provider = None

    def __init__(self, provider, **kwargs):

        self.provider = provider
        self.kwargs = kwargs

        super(ReleaseDownloadList, self).__init__()

    def extend(self, results):
        for r in results:
            self.append(r)

    def append(self, result):
        new_result = self.fillResult(result)
        super(ReleaseDownloadList, self).append(new_result)

    def fillResult(self, result):

        defaults = {
            'id': 0,
            'status': 'busy',
            'downloader': self.provider.getName(),
            'folder': '',
            'files': [],
        }

        return mergeDicts(defaults, result)
