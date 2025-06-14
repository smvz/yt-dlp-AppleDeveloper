#   Copyright 2024 Simon Manning
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import re
import datetime

from json import loads as json_loads
from collections import namedtuple

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import (
    ExtractorError,
    urljoin,
    url_basename
)


class WwdcJsonParser():
    _Event = namedtuple('Event', 'id name images_base')

    def __init__(self, json, ie):
        self._ie = ie
        self._data = json_loads(json)
        self._event = self._get_latest_event()
        self._topics = self._get_topics()

    def get_topic_title(self, topic_slug):
        if not topic_slug:
            return None

        for topic in self._topics:
            if topic.get('slug') == topic_slug:
                return topic.get('title')

        return None

    def get_entries(self, topic_slug = None):
        if topic_slug:
            for topic in self._topics:
                if topic.get('slug') == topic_slug:
                    self._parse_videos([topic])
                    return topic.get('videos')
        else:
            self._parse_videos([self._topics])
            entries = []
            for topic in self._topics:
                entries.extend(topic.get('videos'))
            return entries

        return None

    def _parse_videos(self, topics):
        for topic in topics:
            videos = topic.get('videos')
            if len(videos) == 0:
                videos.extend(self._get_videos(self._event.id, topic.get('id'), topic.get('title')))

    def _get_latest_event(self):
        latest_event = None
        latest_date = datetime.datetime(datetime.MINYEAR, 1, 1, tzinfo=datetime.timezone.utc)
        for event_id, event in self._data.get('events').items():
            event_date = datetime.datetime.fromisoformat("%s" % event.get('startTime'))
            if event_date > latest_date:
                latest_event = event
                latest_date = event_date

        return WwdcJsonParser._Event(event_id, latest_event.get('name'), latest_event.get('imagesPath'))

    def _get_topics(self):
        # Parse all topics for slug and title information. Parsing videos (m3u8) is expensive so we populate
        # that only after a topic's videos are requested.
        topics = []
        for _, topic in self._data.get('topics').items():
            topics.append({
                'id': topic.get('id'),
                'slug': url_basename(topic.get('webPermalink')),
                'title': topic.get('title'),
                'videos': []
            })

        return topics

    def _get_videos(self, event_id, topic_id, topic_title):
        videos = []
        for _, video in self._data.get('videos').items():
            if video.get('eventId') == event_id:
                if video.get('primaryTopicID') == topic_id:
                    videos.append(self._make_video_entry(video, topic_title))

        return videos

    def _make_video_entry(self, video_data, topic_title):
        video_id = video_data.get('id')
        # Build a title to be consistent with the OG title from the /videos/play/... page.
        video_title = f'{video_data.get('title')} - {self._event.name} - Videos - Apple Developer'
        formats, subtitles = self._ie.extract_formats_and_subtitles(video_data.get('media').get('downloadHLS'), video_id)
        return {
            'id': video_id,
            'title': video_title,
            'formats': formats,
            'subtitles': subtitles,
            'categories': [self._event.name, topic_title],
            'thumbnail': self._make_thumbnail_url(video_data.get('staticContentId')),
            'description': video_data.get('description'),
            'timestamp': datetime.datetime.fromisoformat("%s" % video_data.get('originalPublishingDate')).timestamp(),
            'release_timestamp': datetime.datetime.fromisoformat("%s" % video_data.get('contentUpdatedAt')).timestamp()
        }

    def _make_thumbnail_url(self, content_id):
        # https://devimages-cdn.apple.com/wwdc-services/images/3055294D-836B-4513-B7B0-0BC5666246B0/9902/9902_wide_250x141_2x.jpg
        # The JSON is not particularly informative about which variant or size to use and "_2x" is not present at all.
        # This could probably be better but the website has used this form for years so we just build the URL dumbly.
        return f'{self._event.images_base}/{content_id}/{content_id}_wide_250x141_2x.jpg'


class AppleDeveloperIE(InfoExtractor):
    _VALID_URL = r'https?://developer.apple.com/videos/play/(?P<category>[-\w]+)/(?P<id>\d+)'
    _TESTS = [{
        'url': 'https://developer.apple.com/videos/play/wwdc2023/111486/',
        'info_dict': {
            'id': 'wwdc2023-111486',
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
            'id': 'tech-talks-204',
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
        video_id = f'{self._match_valid_url(url).group('category')}-{self._match_id(url)}'
        webpage = self._download_webpage(url, video_id)
        video_url = self._og_search_video_url(webpage, default=None)
        if not video_url:
            raise ExtractorError('Video is unavailable', expected=True)

        formats, subtitles = self._extract_m3u8_formats_and_subtitles(video_url, video_id)

        for format in formats:
            #self.to_screen('%s' % format)
            # If the audio codec is not detected, treat as aac to allow merging to mp4
            if format.get('vcodec') == 'none' and 'acodec' not in format:
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
            'timestamp': datetime.datetime.fromisoformat("%s" % upload_date).timestamp() if upload_date else None,
            'release_timestamp': datetime.datetime.fromisoformat("%s" % published_date).timestamp() if published_date else None
        }


class _AppleWwdcBaseIE(InfoExtractor):
    _BASE_URL = 'https://developer.apple.com'
    _WWDC_DATA_SOURCE = 'https://developer.apple.com/wwdc/services/data/'

    def __init__(self):
        self._jsonParser = None

    @property
    def jsonParser(self):
        if not self._jsonParser:
            json = self._download_webpage(self._WWDC_DATA_SOURCE, 'data_source')
            # Not great creating circular references like this but since yt-dlp runs
            # are not long-lived, it won't be problematic.
            self._jsonParser = WwdcJsonParser(json, self)
        return self._jsonParser

    def playlist_id(self, url):
        raise NotImplementedError('This method must be implemented by subclasses')

    def playlist_title(self, url, webpage):
        raise NotImplementedError('This method must be implemented by subclasses')

    def extract_formats_and_subtitles(self, video_url, video_id):
        return self._extract_m3u8_formats_and_subtitles(video_url, video_id)

    def extract_with_regular_expression(self, webpage, regexp):
        video_urls = [
            urljoin(self._BASE_URL, path)
            for path in re.findall(regexp, webpage)
        ]
        video_urls = list(dict.fromkeys(video_urls))

        entries = [
            self.url_result(video_url)
            for video_url in video_urls
        ]

        return entries

    def _real_extract(self, url):
        raise NotImplementedError('This method must be implemented by subclasses')


class AppleWwdcSessionsIE(_AppleWwdcBaseIE):
    _VALID_URL = r'https?://developer.apple.com/(?P<category>[-\w]+)/sessions-and-labs(/(session-videos|topics(#all)?)?)?$'
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

    def playlist_title(self, url, webpage = None):
        return '%s sessions' % self._match_valid_url(url).group('category')

    def _real_extract(self, url):
        return self.playlist_result(self.jsonParser.get_entries(), self.playlist_id(url), self.playlist_title(url))


class AppleWwdcTopicsIE(_AppleWwdcBaseIE):
    _VALID_URL = r'https?://developer.apple.com/(?P<category>[-\w]+)/sessions-and-labs/topics#(?P<topic>[-\w]+)'
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

    def playlist_title(self, url, webpage = None):
        return self.jsonParser.get_topic_title(self.playlist_id)

    def _real_extract(self, url):
        topic = self._match_valid_url(url).group('topic')
        return self.playlist_result(self.jsonParser.get_entries(topic), self.playlist_id(url), self.playlist_title(url))


class AppleWwdcNewsIE(_AppleWwdcBaseIE):
    _VALID_URL = r'https?://developer.apple.com/news/\?id=(?P<news>[-\w]+)'
    _TESTS = [{
        'url': 'https://developer.apple.com/news/?id=pby7a6ex',
        'info_dict': {
            'id': 'pby7a6ex',
            'title': 'WWDC24 Machine Learning & AI guide - Discover - Apple Developer',
            'playlist_count': 15
        }
    }]

    def playlist_id(self, url):
        return self._match_valid_url(url).group('news')

    def playlist_title(self, url, webpage):
        return '%s' % self._generic_title(url, webpage)

    def _real_extract(self, url):
        playlist_id = self.playlist_id(url)
        webpage = self._download_webpage(url, playlist_id)
        entries = self.extract_with_regular_expression(webpage, r'<a[^>]+href="(https://developer.apple.com/videos/play/(?:[-\w]+)/(?:\d+)[^"]+)"')
        return self.playlist_result(entries, playlist_id, self.playlist_title(url, webpage))
