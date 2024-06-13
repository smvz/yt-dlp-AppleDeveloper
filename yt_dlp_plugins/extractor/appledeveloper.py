import re
from datetime import datetime

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import (
    ExtractorError,
    urljoin
)

class AppleDeveloperIE(InfoExtractor):
    _VALID_URL = r'https?://developer.apple.com/videos/play/(?P<category>[-\w]+)/(?P<id>\d+)'
    _TESTS = [{
        'url': 'https://developer.apple.com/videos/play/wwdc2023/111486/',
        'info_dict': {
            'id': '111486',
            'title': '17 big & little things at WWDC23 - WWDC23 - Videos - Apple Developer',
            'categories': ['wwdc23'],
            'thumbnail': 'https://devimages-cdn.apple.com/wwdc-services/images/D35E0E85-CCB6-41A1-B227-7995ECD83ED5/8745/8745_wide_250x141_2x.jpg',
            'description': 'Here\'s your guide to some of the big (and little) things announced on the first day of WWDC.',
            'timestamp': '1685919600',
            'upload_date': '20230604',
            'release_timestamp': '1685919600',
            'release_date': '20230604'
        }
    },
    {
        'url': 'https://developer.apple.com/videos/play/tech-talks/204/',
        'info_dict': {
            'id': '204',
            'title': 'iOS Storage Best Practices - Tech Talks - Videos - Apple Developer',
            'categories': ['tech-talks'],
            'thumbnail': 'https://devimages-cdn.apple.com/wwdc-services/images/8/2003/2003_wide_250x141_2x.jpg',
            'description': 'Learn tips for keeping your app\'s on-disk storage as organized and optimized as possible. See how to enable direct access to documents in...',
            'timestamp': '1505170800',
            'upload_date': '20170911',
            'release_timestamp': '1505170800',
            'release_date': '20170911'
        }
    }]

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)
        video_url = self._og_search_video_url(webpage, default=None)
        if not video_url:
            raise ExtractorError('Video is unavailable', expected=True)

        formats, subtitles = self._extract_m3u8_formats_and_subtitles(video_url, video_id)

        for format in formats:
            #self.to_screen('%s' % format)
            # If the audio codec is not detected, treat as aac to allow merging to mp4
            if format['vcodec'] == 'none' and 'acodec' not in format:
                format.update({
                    'ext': 'm4a',
                    'acodec': 'aac'
                })

        upload_date = self._html_search_meta('uploadDate', webpage)
        published_date = self._html_search_meta('datePublished', webpage)

        return {
            'id': video_id,
            'title': self._generic_title(url, webpage),
            'formats': formats,
            'subtitles': subtitles,
            'categories': [self._match_valid_url(url).group('category')],
            'thumbnail': self._og_search_thumbnail(webpage),
            'description': self._og_search_description(webpage),
            'timestamp': datetime.fromisoformat("%s" % upload_date).timestamp() if upload_date else None,
            'release_timestamp': datetime.fromisoformat("%s" % published_date).timestamp() if published_date else None
        }


class _AppleWwdcBaseIE(InfoExtractor):
    _BASE_URL = 'https://developer.apple.com'

    def playlist_id(self, url):
        raise NotImplementedError('This method must be implemented by subclasses')

    def playlist_title(self, url, webpage):
        raise NotImplementedError('This method must be implemented by subclasses')

    def extract_with_regular_expression(self, url, regexp):
        playlist_id = self.playlist_id(url)
        webpage = self._download_webpage(url, playlist_id)

        video_urls = [
            urljoin(self._BASE_URL, path)
            for path in re.findall(regexp, webpage)
        ]
        video_urls = list(dict.fromkeys(video_urls))

        entries = [
            self.url_result(video_url)
            for video_url in video_urls
        ]

        return self.playlist_result(entries, playlist_id, self.playlist_title(url, webpage))

    def _real_extract(self, url):
        raise NotImplementedError('This method must be implemented by subclasses')


class AppleWwdcSessionsIE(_AppleWwdcBaseIE):
    _VALID_URL = r'https?://developer.apple.com/(?P<category>[-\w]+)/sessions/'
    _TESTS = [{
        'url': 'https://developer.apple.com/wwdc23/sessions/',
        'info_dict': {
            'id': 'wwdc23',
            'title': 'wwdc23 sessions',
            'playlist_count': 181
        },
        'skip': 'WWDC sessions change every year'
    }]

    def playlist_id(self, url):
        return self._match_valid_url(url).group('category')

    def playlist_title(self, url, webpage):
        return '%s sessions' % self._match_valid_url(url).group('category')

    def _real_extract(self, url):
        return self.extract_with_regular_expression(url, r'<a[^>]+href="(/videos/play/[^"]+)"')


class AppleWwdcTopicsIE(_AppleWwdcBaseIE):
    _VALID_URL = r'https?://developer.apple.com/(?P<category>[-\w]+)/topics/(?P<topic>[-\w]+)'
    _TESTS = [{
        'url': 'https://developer.apple.com/wwdc23/topics/accessibility-inclusion/',
        'info_dict': {
            'id': 'accessibility-inclusion',
            'title': 'Accessibility & Inclusion - Topics - WWDC23',
            'playlist_count': 7
        },
        'skip': 'WWDC topics change every year'
    }]

    def playlist_id(self, url):
        return self._match_valid_url(url).group('topic')

    def playlist_title(self, url, webpage):
        return '%s' % self._generic_title(url, webpage)

    def _real_extract(self, url):
        return self.extract_with_regular_expression(url, r'<a[^>]+href="(/videos/play/[^"]+)"')


class AppleWwdcNewsIE(_AppleWwdcBaseIE):
    _VALID_URL = r'https?://developer.apple.com/news/\?id=(?P<news>[-\w]+)'
    _TESTS = [{
        'url': 'https://developer.apple.com/news/?id=pby7a6ex',
        'info_dict': {
            'id': 'pby7a6ex',
            'title': 'WWDC24 Machine Learning & AI guide - Discover - Apple Developer',
            'playlist_count': 15
        },
        'skip': 'WWDC changes every year'
    }]

    def playlist_id(self, url):
        return self._match_valid_url(url).group('news')

    def playlist_title(self, url, webpage):
        return '%s' % self._generic_title(url, webpage)

    def _real_extract(self, url):
        return self.extract_with_regular_expression(url, r'<a[^>]+href="(https://developer.apple.com/(?:[-\w]+)/(?:\d+)[^"]+)"')
