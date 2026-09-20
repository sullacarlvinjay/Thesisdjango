"""A systematic accessibility audit, run against every rendered portal page.

The pieces were already here — a skip link, sr-only labels, focus rings,
reduced-motion, AA contrast gated in CI — but nothing checked them all in one
place, so which page had what was a matter of when it was last worked on. These
cases ask the same questions of all sixteen pages at once, which is the only way
the answer stays true for the next page somebody adds.

Static analysis of rendered HTML, not a browser. It catches the failures that
are structural — a control nobody can name, a heading level that skips, an id
pointed at from a label that does not exist. It cannot catch the ones that are
visual or behavioural, and does not pretend to: contrast is asserted in
api/test_contrast.py, and keyboard order still wants a person.
"""

import re
from html.parser import HTMLParser

from django.test import TestCase

from .fixtures_portal import render_every_page

VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link',
        'meta', 'param', 'source', 'track', 'wbr'}

NAMED_BY = ('aria-label', 'aria-labelledby', 'title')

LABELLABLE = {'input', 'select', 'textarea'}

UNLABELLED_INPUTS = {'hidden', 'submit', 'reset', 'button', 'image'}


class Node:
    """One element, its attributes, its children and the text under it."""

    __slots__ = ('tag', 'attrs', 'children', 'parent', 'text')

    def __init__(self, tag, attrs, parent):
        self.tag = tag
        self.attrs = attrs
        self.children = []
        self.parent = parent
        self.text = []

    def get(self, name, default=''):
        return self.attrs.get(name, default)

    def has(self, name):
        return name in self.attrs

    def own_text(self):
        """Every run of text under this element, flattened."""
        found = list(self.text)
        for child in self.children:
            found.extend(child.own_text())
        return ' '.join(part for part in found if part)

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    def ancestors(self):
        node = self.parent
        while node is not None:
            yield node
            node = node.parent

    def where(self):
        """A short path, so a failure says which element it means."""
        trail = []
        for node in [self, *list(self.ancestors())[:3]]:
            mark = node.tag
            if node.get('id'):
                mark += f"#{node.get('id')}"
            elif node.get('name'):
                mark += f"[name={node.get('name')}]"
            elif node.get('class'):
                mark += f".{node.get('class').split()[0]}"
            trail.append(mark)
        return ' < '.join(trail)


class Tree(HTMLParser):
    """The smallest parser that answers the questions below."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('#document', {}, None)
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, {k: (v or '') for k, v in attrs}, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        node = Node(tag, {k: (v or '') for k, v in attrs}, self.stack[-1])
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return

    def handle_data(self, data):
        if data.strip():
            self.stack[-1].text.append(data.strip())


def parse(html):
    tree = Tree()
    tree.feed(html)
    return tree.root


def named(node, ids):
    """Whether a control or widget has any accessible name at all."""
    if any(node.get(attr).strip() for attr in NAMED_BY):
        if node.get('aria-labelledby'):
            return any(ref in ids for ref in node.get('aria-labelledby').split())
        return True
    return False


class AccessibilityTest(TestCase):
    """One rendered copy of every page, asked the same questions."""

    maxDiff = None

    @classmethod
    def setUpTestData(cls):
        cls.pages = render_every_page()
        cls.trees = {name: parse(html) for name, html in cls.pages.items()}

    def each_page(self):
        for name in sorted(self.trees):
            yield name, self.trees[name]

    def ids_on(self, tree):
        return {node.get('id') for node in tree.walk() if node.get('id')}

    def test_every_page_in_the_list_still_answers(self):
        missing = [name for name, _url, _who in
                   __import__('api.fixtures_portal', fromlist=['PAGES']).PAGES
                   if name not in self.pages]
        self.assertEqual(
            missing, [],
            'these pages stopped rendering, so nothing below checked them')

    def test_every_image_says_what_it_is_or_says_it_is_decoration(self):
        for name, tree in self.each_page():
            for node in tree.walk():
                if node.tag != 'img':
                    continue
                with self.subTest(page=name, at=node.where()):
                    self.assertTrue(
                        node.has('alt'),
                        'an <img> with no alt is read out as its file name')

    def test_every_form_control_has_a_name_somebody_can_hear(self):
        for name, tree in self.each_page():
            ids = self.ids_on(tree)
            labelled = {node.get('for') for node in tree.walk()
                        if node.tag == 'label' and node.get('for')}
            for node in tree.walk():
                if node.tag not in LABELLABLE:
                    continue
                if node.tag == 'input' and node.get('type') in UNLABELLED_INPUTS:
                    continue
                if node.get('aria-hidden') == 'true':
                    continue
                wrapped = any(a.tag == 'label' for a in node.ancestors())
                with self.subTest(page=name, at=node.where()):
                    self.assertTrue(
                        named(node, ids) or wrapped
                        or (node.get('id') and node.get('id') in labelled),
                        'this control is announced as just "edit text" — it '
                        'needs a <label for>, a wrapping <label>, or an '
                        'aria-label')

    def test_every_button_and_link_says_what_it_does(self):
        for name, tree in self.each_page():
            ids = self.ids_on(tree)
            for node in tree.walk():
                if node.tag not in ('button', 'a'):
                    continue
                if node.tag == 'a' and not node.has('href'):
                    continue
                if node.get('aria-hidden') == 'true':
                    continue
                with self.subTest(page=name, at=node.where()):
                    self.assertTrue(
                        node.own_text().strip() or named(node, ids),
                        'an icon-only control with no aria-label is announced '
                        'as "button", which says nothing about what it does')

    def test_every_page_has_exactly_one_first_level_heading(self):
        for name, tree in self.each_page():
            tops = [node for node in tree.walk() if node.tag == 'h1']
            with self.subTest(page=name):
                self.assertEqual(
                    len(tops), 1,
                    'a page is navigated by its headings; it needs one h1 '
                    'naming it, and only one')

    def test_no_heading_level_is_skipped(self):
        for name, tree in self.each_page():
            levels = [int(node.tag[1]) for node in tree.walk()
                      if re.fullmatch(r'h[1-6]', node.tag)]
            previous = 0
            for level in levels:
                with self.subTest(page=name, heading=f'h{level}'):
                    self.assertLessEqual(
                        level, previous + 1 if previous else 1,
                        f'h{previous} is followed by h{level}; a screen reader '
                        'reports that as a missing section')
                previous = level

    def test_no_id_is_used_twice(self):
        for name, tree in self.each_page():
            seen, twice = set(), set()
            for node in tree.walk():
                node_id = node.get('id')
                if not node_id:
                    continue
                if node_id in seen:
                    twice.add(node_id)
                seen.add(node_id)
            with self.subTest(page=name):
                self.assertEqual(
                    sorted(twice), [],
                    'a repeated id makes every label, aria-labelledby and '
                    'anchor pointing at it resolve to whichever came first')

    def test_every_reference_points_at_something_that_exists(self):
        attributes = ('for', 'aria-labelledby', 'aria-describedby',
                      'aria-controls')
        for name, tree in self.each_page():
            ids = self.ids_on(tree)
            for node in tree.walk():
                for attribute in attributes:
                    value = node.get(attribute).strip()
                    if not value:
                        continue
                    if attribute == 'for' and node.tag != 'label':
                        continue
                    for ref in value.split():
                        with self.subTest(page=name, at=node.where(),
                                          attribute=attribute):
                            self.assertIn(
                                ref, ids,
                                f'{attribute}="{ref}" names an element that is '
                                'not on the page, so the association is silent')

    def test_every_table_gives_its_columns_headers(self):
        for name, tree in self.each_page():
            for node in tree.walk():
                if node.tag != 'table':
                    continue
                headers = [n for n in node.walk() if n.tag == 'th']
                with self.subTest(page=name, at=node.where()):
                    self.assertTrue(
                        headers,
                        'a table of <td> alone is read cell by cell with '
                        'nothing to say which column each one is in')

    def test_nothing_jumps_the_keyboard_order(self):
        for name, tree in self.each_page():
            for node in tree.walk():
                value = node.get('tabindex').strip()
                if not value:
                    continue
                with self.subTest(page=name, at=node.where()):
                    self.assertLessEqual(
                        int(value), 0,
                        'a positive tabindex pulls this element out of the '
                        'document order and ahead of everything else')

    def test_a_link_that_opens_a_new_tab_says_so_and_is_not_a_way_back_in(self):
        for name, tree in self.each_page():
            ids = self.ids_on(tree)
            for node in tree.walk():
                if node.tag != 'a' or node.get('target') != '_blank':
                    continue
                with self.subTest(page=name, at=node.where()):
                    self.assertIn(
                        'noopener', node.get('rel'),
                        'target=_blank without rel=noopener hands the opened '
                        'page a handle on this one')
                    spoken = (node.own_text() + ' ' + node.get('aria-label')
                              + ' ' + node.get('title')).lower()
                    self.assertTrue(
                        named(node, ids) or 'new tab' in spoken
                        or 'new window' in spoken,
                        'a link that replaces nothing and opens elsewhere '
                        'should say so before it is followed')
