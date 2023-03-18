import hashlib
import json
import re
from datetime import datetime

import yaml


rst_sep = '.. end-entry'
md_sep = '<!--- end-entry --->'


# Find heading points.
def _is_rst_heading(s):
    s = s.strip()
    return s.startswith('=') and s.endswith('=')


def _is_md_heading(s):
    s = s.strip()
    return s.startswith('# ') or s.startswith('## ')


def get_entries_from_md(md):
    """ Parse many entries out of markdown text.
    """
    md = md.strip()
    if not md:
        return []

    # Markdown entries are terminated by a line containing only this string.
    texts = md.split(md_sep)
    if not texts[-1]:
        texts.pop()

    entries = []

    for t in texts:
        entries.append(Entry.createFromMd(t))

    return entries


def get_entries_from_rst(rst):
    rst = rst.strip()
    if not rst:
        return []

    texts = rst.split(rst_sep)
    if not texts[-1]:
        texts.pop()

    entries = []
    for t in texts:
        entries.append(Entry.createFromRst(t))

    return entries


def str_to_entries(text, entry_format):
    """ Convert a str to a list of entries.

    The return from this function can be passed to entries_to_str.

    Args:
        text: Text to convert to entries.
        entry_format: 'rst' or 'md'.

    Returns:
        A list of Entry references.
    """
    entries = []
    if entry_format == 'rst':
        entries = get_entries_from_rst(text)
    elif entry_format == 'md':
        entries = get_entries_from_md(text)

    return entries


def entries_to_str(entries, entry_format, headings=None):
    """ Return many entries as a str.

    The output from this function can be passed to str_to_entries.

    Args:
        entries: List of entries to print.
        entry_format: 'rst' or 'md'.

    Returns:
        A str representing the entries
    """
    text = ''
    if entry_format == 'rst':
        text = [x.getRst(headings) for x in entries]
        text = f'\n{rst_sep}\n\n\n'.join(sorted([x for x in text if x]))
    elif entry_format == 'md':
        text = [x.getMd(headings) for x in entries]
        text = f'\n{md_sep}\n\n\n'.join(sorted([x for x in text if x]))

    return text


def _gen_id(title):
    dt = datetime.today()
    s = '{}-{}-{}_{}-{}-{}-{}'.format(
        dt.year, dt.month, dt.day,
        dt.hour, dt.minute, dt.second, dt.microsecond)
    h = hashlib.sha1()
    h.update(bytes(title + s, 'utf-8'))
    return h.hexdigest() + '-' + s


class Entry:
    """ Represents a single entry from a journal.
    """
    def __init__(self, title, headings, attrs):
        """ Create a new entry.

        Args:
            title: Title of the entry.
            headings: Dictionary of subheadings. Each heading is paired with
                a string for its entry.
            attrs: Dictionary of metadata for the entry.
        """
        self.title = title
        self.headings = {k: v for k, v in headings.items()}
        self.attrs = attrs

        if 'id' not in self.attrs or not self.attrs['id'].strip():
            self.attrs['id'] = _gen_id(title)

        if 'tags' not in self.attrs or not self.attrs['tags']:
            self.attrs['tags'] = []

        self.refresh()

    def addHeadings(self, headings):
        """ Add new headings to the entry.

        Args:
            headings: List of headings to add. No content will be added.
        """
        headings = [x for x in headings]
        for heading in headings:
            if heading not in self.headings:
                self.headings[heading] = ''

    @classmethod
    def createBlankEntry(cls, title):
        """ Create a blank entry. Still needs a title.

        Args:
            title: Title of the entry.
        """
        return Entry(title, dict(), dict())

    @classmethod
    def createFromMd(cls, md):
        """ Create a new Entry from markdown text.

        The text will be parsed to derive key-value entries where the key
        is the heading and the value is the subsequent text.

        The title of the entry is expected to be a markdown level-1 heading
        (# ) This is followed by the entry's notes, which is then
        succeeded by the rest of the entry's headings, which are expected
        to be RST level 2 headings (## ).

        Args:
            md: Markdown text from which to create the entry.

        Returns:
            A new Entry.

        Raises:
            ValueError if the markdown could not create a valid Entry.
        """
        md = md.strip()

        if not md:
            raise ValueError('The entry was empty.')

        ptr = 0

        title = ''
        headings = {}

        attr_header = '<!--- attributes --->'
        md = md.split(attr_header)
        if len(md) == 1:
            md.append('')

        # split out attrs and actual entry text
        attrs = yaml.safe_load(md[-1].strip())
        md = attr_header.join(md[:-1]).splitlines()

        # Find the headings and content.
        heading_pts = [x for x, y in enumerate(md) if _is_md_heading(y)]

        # Find the title.
        if not heading_pts:
            raise ValueError('No title in entry.')

        heading_pts.append(len(md))

        title = ' '.join(md[heading_pts[0]].split()[1:])

        # Gather notes
        headings['notes'] = '\n'.join(md[1:heading_pts[1]])

        # ... and delete the "notes" entry if no notes were entered.
        if not headings['notes'].strip():
            del(headings['notes'])

        # Get the rest
        for ptr in range(1, len(heading_pts) - 1):
            heading = ''.join(md[heading_pts[ptr]].split('##')[1:]).strip()
            content_start = heading_pts[ptr] + 1
            content_end = heading_pts[ptr + 1]
            headings[heading] = '\n'.join(md[content_start:content_end])

        return Entry(title, headings, attrs)

    @classmethod
    def createFromRst(cls, rst):
        """ Create a new Entry from RST text.

        The RST will be parsed to derive key-value entries where the key
        is the heading and the value is the subsequent text.

        The title of the entry is expected to be an RST level-1 heading
        (=====). This is followed by the entry's notes, which is then
        succeeded by the rest of the entry's headings, which are expected
        to be RST level 2 headings (-----).

        Args:
            rst: RST-formatted text from which to create the entry.

        Returns:
            A new Entry.

        Raises:
            ValueError if the RST could not create a valid Entry.
        """
        rst = rst.strip()

        if not rst:
            raise ValueError('The entry was completely empty.')

        ptr = 0

        title = ''
        headings = {}

        # Split out the attrs and content.
        attr_header = '.. code-block:: yaml'
        rst = rst.split(attr_header)
        if len(rst) == 1:
            rst.append('')

        attrs = yaml.safe_load(rst[-1].strip())
        rst = attr_header.join(rst[:-1]).splitlines()

        # Strip the first line of === if it exists.
        if _is_rst_heading(rst[0]):
            rst = rst[1:]

        # Find the lines in the text that are heading markers.
        heading_pts = [x - 1 for x, y in enumerate(rst) if _is_rst_heading(y)]

        # First heading marker is the title.
        if not heading_pts or heading_pts[0] == -1:
            raise ValueError('No title in entry.')

        heading_pts.append(len(rst))

        title = rst[heading_pts[0]].strip()

        # Gather notes
        headings['notes'] = '\n'.join(rst[heading_pts[0] + 2:heading_pts[1]])

        # ... and delete the "notes" entry if no notes were entered.
        if not headings['notes'].strip():
            del(headings['notes'])

        # Get the rest
        for ptr in range(1, len(heading_pts) - 1):
            heading = rst[heading_pts[ptr]]
            content_start = heading_pts[ptr] + 2
            content_end = heading_pts[ptr + 1]
            headings[heading] = '\n'.join(rst[content_start:content_end])

        return Entry(title, headings, attrs)

    def refresh(self):
        """ Make minor corrections

        Tags should be sorted.
        """
        self.attrs['tags']= sorted(list(set([x for x in self.attrs['tags']])))

    def update(self, new_entry, exp_headings=None):
        """ Update an entry.

        The title and tags of this entry will be replaced, and new
        headings will be added, while any headings which were expected
        to be in the new entry (but weren't) will be deleted from this
        entry.

        Args:
            new_entry: Other entry instance whose values will be used.
            exp_headings: If a heading is listed here, but is not found in
                rst, then the heading will be deleted from the entry.

        Raises:
            See createFromRst.
        """
        exp_headings = exp_headings or []

        # Update this entry.
        old_id = self.attrs['id']
        self.title = new_entry.title
        self.attrs = new_entry.attrs.copy()
        self.attrs['id'] = old_id

        if not exp_headings:
            self.headings = new_entry.headings
        else:
            for heading in exp_headings:
                if heading not in new_entry.headings and heading in self.headings:
                    del(self.headings[heading])

            self.headings.update(new_entry.headings)

        self.refresh()

    def getMd(self, headings=None, force=False):
        display = False

        headings = headings or []
        headings = headings or self.headings
        headings = [x.lower() for x in headings]

        s = []
        s.append('# ' + self.title)

        if 'notes' in headings:
            display = True
            s.append(self.headings['notes'].rstrip())
            s.append('')

        # case-insensitive search
        lookup_headings = {k.lower(): k for k in self.headings}
        for heading in headings:
            if heading == 'notes' or heading not in lookup_headings:
                continue

            display = True
            s.append('## ' + lookup_headings[heading])
            s.append(self.headings[lookup_headings[heading]].rstrip())
            s.append('')

        # No content, but add an empty line for good-looks
        if not display and force:
            s.append('')

        # Append the attributes
        s.append('')
        s.append('<!--- attributes --->')
        s += ['    ' + x for x in ['---'] + yaml.dump(self.attrs).splitlines()]
        s.append('')

        if display or force:
            return '\n'.join(s)
        else:
            return ''

    def getRst(self, headings=None, force=False):
        """ Display this entry in RST format.

        Args:
            headings: Only show the listed headings. Will show all
                headings if this value is None.
            force: Force the display even if there is no content.

        Returns:
            An RST string representing the content of this entry.

        Raises:
            KeyError if a heading wasn't in self.headings.
        """
        display = False

        headings = headings or []
        headings = headings or self.headings
        headings = [x.lower() for x in headings]

        s = []
        s.append('=' * (len(self.title) + 2))
        s.append(' ' + self.title)
        s.append('=' * (len(self.title) + 2))

        if 'notes' in headings:
            display = True
            s.append(self.headings['notes'].rstrip())
            s.append('')

        # case-insensitive search
        lookup_headings = {k.lower(): k for k in self.headings}
        for heading in headings:
            if heading == 'notes' or heading not in lookup_headings:
                continue

            display = True
            s.append(lookup_headings[heading])
            s.append('=' * len(lookup_headings[heading]))
            s.append(self.headings[lookup_headings[heading]].rstrip())
            s.append('')

        # No content, but add an empty line for good-looks
        if not display and force:
            s.append('')

        # Append the attributes
        s.append('')
        s.append('.. code-block:: yaml')
        s.append('')
        s += ['    ' + x for x in ['---'] + yaml.dump(self.attrs).splitlines()]

        # Will become trailing newline
        s.append('')

        if display or force:
            return '\n'.join(s)
        else:
            return ''

    def __eq__(self, o):
        return self.title == o.title

    def __lt__(self, o):
        return self.title.lower() < o.title.lower()
