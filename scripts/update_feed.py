#!/usr/bin/env python3
"""Fetch the original podcast RSS and publish small newest-first Sonix feeds."""
from copy import deepcopy
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
import sys
import urllib.request
import xml.etree.ElementTree as ET

SOURCE = (
    'https://www.omnycontent.com/d/playlist/'
    '2446592a-b80e-4d28-a4fd-ae4c0140ac11/'
    '9afe58f0-d402-4e05-a5ce-aead00a0ba96/'
    'fd25a142-cbf1-4f2b-9146-aead00a0bab7/podcast.rss'
)

# Keep namespaces readable and avoid arbitrary ns0/ns1 prefixes.
for prefix, uri in (
    ('itunes', 'http://www.itunes.com/dtds/podcast-1.0.dtd'),
    ('content', 'http://purl.org/rss/1.0/modules/content/'),
    ('atom', 'http://www.w3.org/2005/Atom'),
    ('media', 'http://search.yahoo.com/mrss/'),
    ('googleplay', 'http://www.google.com/schemas/play-podcasts/1.0'),
    ('podcast', 'https://podcastindex.org/namespace/1.0'),
    ('dc', 'http://purl.org/dc/elements/1.1/'),
):
    ET.register_namespace(prefix, uri)


def date_key(item):
    raw = item.findtext('pubDate')
    if not raw:
        raise ValueError('An episode has no pubDate')
    dt = parsedate_to_datetime(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('public')
    request = urllib.request.Request(
        SOURCE,
        headers={'User-Agent': 'Mozilla/5.0 (compatible; SonixRSSUpdater/1.0)',
                 'Accept': 'application/rss+xml, application/xml, text/xml, */*'},
    )
    with urllib.request.urlopen(request, timeout=75) as response:
        data = response.read(15 * 1024 * 1024 + 1)
    if len(data) > 15 * 1024 * 1024:
        raise ValueError('Source feed unexpectedly exceeds 15 MB')
    original = ET.fromstring(data)
    if original.tag != 'rss':
        raise ValueError('Source is not RSS')
    channel = original.find('channel')
    if channel is None:
        raise ValueError('RSS channel is missing')
    episodes = list(channel.findall('item'))
    if len(episodes) < 100:
        raise ValueError(f'Only {len(episodes)} episodes; refusing to replace feeds')
    if any(item.find('enclosure') is None for item in episodes):
        raise ValueError('At least one episode lacks an audio enclosure')
    episodes.sort(key=date_key, reverse=True)
    output.mkdir(parents=True, exist_ok=True)

    for limit in (50, 100):
        rss = deepcopy(original)
        ch = rss.find('channel')
        for item in list(ch.findall('item')):
            ch.remove(item)
        for item in episodes[:limit]:
            ch.append(deepcopy(item))
        filename = output / f'la_escobula_latest_{limit}.rss'
        ET.ElementTree(rss).write(filename, encoding='utf-8', xml_declaration=True)
        verified = ET.parse(filename).getroot().find('channel').findall('item')
        assert len(verified) == limit
        print(f'Created {filename}: {len(verified)} episodes; '
              f'newest {verified[0].findtext("pubDate")}')


if __name__ == '__main__':
    main()
