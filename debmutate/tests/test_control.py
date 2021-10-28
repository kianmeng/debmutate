#!/usr/bin/python
# Copyright (C) 2018 Jelmer Vernooij
# This file is a part of debmutate.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

"""Tests for lintian_brush.control."""

import os

from . import (
    TestCase,
    TestCaseInTempDir,
    )

from ..control import (
    _cdbs_resolve_conflict,
    add_dependency,
    drop_dependency,
    ensure_exact_version,
    ensure_minimum_version,
    ensure_some_version,
    ensure_relation,
    get_relation,
    iter_relations,
    is_relation_implied,
    is_dep_implied,
    update_control,
    PkgRelation,
    format_relations,
    parse_relations,
    delete_from_list,
    ControlEditor,
    parse_standards_version,
    )
from ..deb822 import has_deb822_repro
from ..reformatting import (
    GeneratedFile,
    FormattingUnpreservable,
    )


class UpdateControlTests(TestCaseInTempDir):

    def test_do_not_edit(self):
        self.build_tree_contents([('debian/', ), ('debian/control', """\
# DO NOT EDIT
# This file was generated by blah

Source: blah
Testsuite: autopkgtest

""")])

        def source_cb(c):
            c['Source'] = 'blah1'
        self.assertRaises(
            GeneratedFile, update_control, source_package_cb=source_cb)

    def test_add_binary(self):
        self.build_tree_contents([('debian/', ), ('debian/control', """\
Source: blah
Testsuite: autopkgtest

Package: blah
Description: Some description
 And there are more lines
 And more lines
""")])
        with ControlEditor('debian/control') as editor:
            editor.add_binary(
                {'Package': 'foo', 'Description': 'A new package foo'})
            self.assertEqual(
                [b['Package'] for b in editor.binaries], ['blah', 'foo'])

    def test_list_binaries(self):
        self.build_tree_contents([('debian/', ), ('debian/control', """\
Source: blah
Testsuite: autopkgtest

Package: blah
Description: Some description
 And there are more lines
 And more lines
""")])
        with ControlEditor('debian/control') as editor:
            self.assertEqual(list(editor.binaries)[0]['Package'], 'blah')

    def test_create(self):
        self.build_tree_contents([('debian/', )])
        with ControlEditor.create('debian/control') as editor:
            editor.source['Source'] = 'foo'
        self.assertFileEqual("""\
Source: foo
""", 'debian/control')

    def test_do_not_edit_no_change(self):
        self.build_tree_contents([('debian/', ), ('debian/control', """\
# DO NOT EDIT
# This file was generated by blah

Source: blah
Testsuite: autopkgtest

""")])
        update_control()

    def test_unpreservable(self):
        self.build_tree_contents([('debian/', ), ('debian/control', """\
Source: blah
# A comment
Testsuite: autopkgtest

""")])

        def update_source(control):
            control["NewField"] = "New Field"
        if has_deb822_repro:
            update_control(source_package_cb=update_source)
        else:
            self.assertRaises(
                FormattingUnpreservable, update_control,
                source_package_cb=update_source)

    def test_merge3(self):
        self.build_tree_contents([('debian/', ), ('debian/control', """\
Source: blah
Testsuite: autopkgtest

Package: blah
Description: Some description
 And there are more lines
 And more lines
# A comment
Multi-Arch: foreign
""")])

        def update_source(control):
            control["NewField"] = "New Field"

        try:
            import merge3  # noqa: F401
        except ModuleNotFoundError:
            has_merge3 = False
        else:
            has_merge3 = (merge3.__version__ >= (0, 0, 7))
        if has_merge3:
            update_control(source_package_cb=update_source)
            self.assertFileEqual("""\
Source: blah
Testsuite: autopkgtest
NewField: New Field

Package: blah
Description: Some description
 And there are more lines
 And more lines
# A comment
Multi-Arch: foreign
""", 'debian/control')
        else:
            self.assertRaises(
                FormattingUnpreservable, update_control,
                source_package_cb=update_source)

    def test_modify_source(self):
        self.build_tree_contents([('debian/', ), ('debian/control', """\
Source: blah
Testsuite: autopkgtest
""")])

        def add_header(control):
            control["XS-Vcs-Git"] = "git://github.com/example/example"
        self.assertTrue(update_control(source_package_cb=add_header))
        self.assertFileEqual("""\
Source: blah
Testsuite: autopkgtest
XS-Vcs-Git: git://github.com/example/example
""", 'debian/control')

    def test_modify_binary(self):
        self.build_tree_contents([('debian/', ), ('debian/control', """\
Source: blah
Testsuite: autopkgtest

Package: libblah
Section: extra
""")])

        def add_header(control):
            control["Arch"] = "all"
        self.assertTrue(update_control(binary_package_cb=add_header))
        self.assertFileEqual("""\
Source: blah
Testsuite: autopkgtest

Package: libblah
Section: extra
Arch: all
""", 'debian/control')

    def test_doesnt_strip_whitespace(self):
        self.build_tree_contents([('debian/', ), ('debian/control', """\
Source: blah
Testsuite: autopkgtest

""")])
        self.assertFalse(update_control())
        self.assertFileEqual("""\
Source: blah
Testsuite: autopkgtest

""", 'debian/control')

    def test_update_template(self):
        self.build_tree_contents([('debian/', ), ('debian/control', """\
# DO NOT EDIT
# This file was generated by blah

Source: blah
Testsuite: autopkgtest
Uploaders: Jelmer Vernooij <jelmer@jelmer.uk>

"""), ('debian/control.in', """\
Source: blah
Testsuite: autopkgtest
Uploaders: @lintian-brush-test@

""")])

        with ControlEditor() as updater:
            updater.source['Testsuite'] = 'autopkgtest8'
            updater.changes()
        self.assertFileEqual("""\
Source: blah
Testsuite: autopkgtest8
Uploaders: @lintian-brush-test@
""", "debian/control.in", strip_trailing_whitespace=True)
        self.assertFileEqual("""\
Source: blah
Testsuite: autopkgtest8
Uploaders: testvalue
""", "debian/control", strip_trailing_whitespace=True)

    def test_update_template_only(self):
        self.build_tree_contents([('debian/', ), ('debian/control.in', """\
Source: blah
Testsuite: autopkgtest
Uploaders: @lintian-brush-test@

""")])

        with ControlEditor() as updater:
            updater.source['Testsuite'] = 'autopkgtest8'
            updater.changes()
        self.assertFileEqual("""\
Source: blah
Testsuite: autopkgtest8
Uploaders: @lintian-brush-test@
""", "debian/control.in", strip_trailing_whitespace=True)
        self.assertFalse(os.path.exists('debian/control'))

    def test_update_cdbs_template(self):
        self.build_tree_contents([('debian/', ), ('debian/control', """\
Source: blah
Testsuite: autopkgtest
Build-Depends: some-foo, libc6

"""), ('debian/control.in', """\
Source: blah
Testsuite: autopkgtest
Build-Depends: @cdbs@, libc6

""")])

        with ControlEditor() as updater:
            updater.source['Build-Depends'] = 'some-foo, libc6, some-bar'
        self.assertFileEqual("""\
Source: blah
Testsuite: autopkgtest
Build-Depends: some-foo, libc6, some-bar
""", "debian/control", strip_trailing_whitespace=True)
        self.assertFileEqual("""\
Source: blah
Testsuite: autopkgtest
Build-Depends: @cdbs@, libc6, some-bar
""", "debian/control.in", strip_trailing_whitespace=True)

    def test_description_stays_last(self):
        self.build_tree_contents([('debian/', ), ('debian/control', """\
Source: blah
Testsuite: autopkgtest

Package: libblah
Section: extra
Description: foo
 bar

""")])

        def add_header(control):
            control["Arch"] = "all"
        self.assertTrue(update_control(binary_package_cb=add_header))
        self.assertFileEqual("""\
Source: blah
Testsuite: autopkgtest

Package: libblah
Section: extra
Arch: all
Description: foo
 bar
""", 'debian/control', strip_trailing_whitespace=True)


class ParseRelationsTests(TestCase):

    def test_empty(self):
        self.assertEqual([], parse_relations(''))
        self.assertEqual([('\n', [], '')], parse_relations('\n'))

    def test_simple(self):
        self.assertEqual(
                [('', [PkgRelation('debhelper')], '')],
                parse_relations('debhelper'))
        self.assertEqual(
                [('  \n', [PkgRelation('debhelper')], '')],
                parse_relations('  \ndebhelper'))
        self.assertEqual(
                [('  \n', [PkgRelation('debhelper')], ' \n')],
                parse_relations('  \ndebhelper \n'))


class FormatRelationsTests(TestCase):

    def test_empty(self):
        self.assertEqual(
                '',
                format_relations([('', [], '')]))
        self.assertEqual(
                '',
                format_relations([('', [], '\n')]))
        self.assertEqual(
                '',
                format_relations([('\n ', [], '')]))

    def test_simple(self):
        self.assertEqual(
                'debhelper',
                format_relations([('', [PkgRelation('debhelper')], '')]))
        self.assertEqual(
                format_relations([('  \n', [PkgRelation('debhelper')], '')]),
                '  \ndebhelper')
        self.assertEqual(
                format_relations(
                    [('  \n', [PkgRelation('debhelper')], ' \n')]),
                '  \ndebhelper ')

    def test_multiple(self):
        self.assertEqual(
                'debhelper, blah',
                format_relations([('', [PkgRelation('debhelper')], ''),
                                 (' ', [PkgRelation('blah')], '')]))


class EnsureMinimumVersionTests(TestCase):

    def test_added(self):
        self.assertEqual(
            'debhelper (>= 9)', ensure_minimum_version('', 'debhelper', '9'))
        self.assertEqual(
            'blah, debhelper (>= 9)',
            ensure_minimum_version('blah', 'debhelper', '9'))

    def test_unchanged(self):
        self.assertEqual(
            'debhelper (>= 9)', ensure_minimum_version(
                'debhelper (>= 9)', 'debhelper', '9'))
        self.assertEqual(
            'debhelper (= 9)', ensure_minimum_version(
                'debhelper (= 9)', 'debhelper', '9'))
        self.assertEqual(
            'debhelper (>= 9)', ensure_minimum_version(
                'debhelper (>= 9)', 'debhelper', '9~'))

    def test_updated(self):
        self.assertEqual(
            'debhelper (>= 9)',
            ensure_minimum_version('debhelper', 'debhelper', '9'))
        self.assertEqual(
            'blah, debhelper (>= 9)',
            ensure_minimum_version('blah, debhelper', 'debhelper', '9'))
        self.assertEqual(
            'blah, debhelper (>= 9)',
            ensure_minimum_version('blah, debhelper (>= 8)', 'debhelper', '9'))
        self.assertEqual(
            'blah, debhelper (>= 9)',
            ensure_minimum_version(
                'blah, debhelper (>= 8), debhelper (>= 8.1) | dh-systemd',
                'debhelper', '9'))
        self.assertEqual(
            'blah, debhelper (>= 9), debhelper (>= 10) | dh-systemd',
            ensure_minimum_version(
                'blah, debhelper (>= 8), debhelper (>= 10) | dh-systemd',
                'debhelper', '9'))


class EnsureRelationTests(TestCase):

    def test_added(self):
        self.assertEqual(
            'debhelper (>= 9)', ensure_relation('', 'debhelper (>= 9)'))
        self.assertEqual(
            'blah, debhelper (>= 9)',
            ensure_relation('blah', 'debhelper (>= 9)'))

    def test_unchanged(self):
        self.assertEqual(
            'debhelper (>= 9)', ensure_relation(
                'debhelper (>= 9)', 'debhelper (>= 9)'))
        self.assertEqual(
            'debhelper (= 9)', ensure_relation(
                'debhelper (= 9)', 'debhelper (>= 9)'))
        self.assertEqual(
            'debhelper (>= 9)', ensure_relation(
                'debhelper (>= 9)', 'debhelper (>= 9~)'))

    def test_updated(self):
        self.assertEqual(
            'debhelper (>= 9)',
            ensure_relation('debhelper', 'debhelper (>= 9)'))
        self.assertEqual(
            'blah, debhelper (>= 9)',
            ensure_relation('blah, debhelper', 'debhelper (>= 9)'))
        self.assertEqual(
            'blah, debhelper (>= 9)',
            ensure_relation('blah, debhelper (>= 8)', 'debhelper (>= 9)'))
        self.assertEqual(
            'blah, debhelper (>= 9)',
            ensure_relation(
                'blah, debhelper (>= 8), debhelper (>= 8.1) | dh-systemd',
                'debhelper (>= 9)'))
        self.assertEqual(
            'blah, debhelper (>= 9), debhelper (>= 10) | dh-systemd',
            ensure_relation(
                'blah, debhelper (>= 8), debhelper (>= 10) | dh-systemd',
                'debhelper (>= 9)'))


class EnsureSomeVersionTests(TestCase):

    def test_added(self):
        self.assertEqual(
            'debhelper', ensure_some_version('', 'debhelper'))
        self.assertEqual(
            'blah, debhelper',
            ensure_some_version('blah', 'debhelper'))

    def test_unchanged(self):
        self.assertEqual(
            'debhelper (>= 9)', ensure_some_version(
                'debhelper (>= 9)', 'debhelper'))
        self.assertEqual(
            'debhelper (= 9)', ensure_some_version(
                'debhelper (= 9)', 'debhelper'))
        self.assertEqual(
            'debhelper (>= 9)', ensure_some_version(
                'debhelper (>= 9)', 'debhelper'))
        self.assertEqual(
            'debhelper', ensure_some_version(
                'debhelper', 'debhelper'))


class EnsureExactVersionTests(TestCase):

    def test_added(self):
        self.assertEqual(
            'debhelper (= 9)', ensure_exact_version('', 'debhelper', '9'))
        self.assertEqual(
            'blah, debhelper (= 9)',
            ensure_exact_version('blah', 'debhelper', '9'))

    def test_unchanged(self):
        self.assertEqual(
            'debhelper (= 9)', ensure_exact_version(
                'debhelper (= 9)', 'debhelper', '9'))

    def test_updated(self):
        self.assertEqual(
            'debhelper (= 9)', ensure_exact_version(
                'debhelper (>= 9)', 'debhelper', '9'))
        self.assertEqual(
            'debhelper (= 9)',
            ensure_exact_version('debhelper', 'debhelper', '9'))
        self.assertEqual(
            'blah, debhelper (= 9)',
            ensure_exact_version('blah, debhelper', 'debhelper', '9'))
        self.assertEqual(
            'blah, debhelper (= 9)',
            ensure_exact_version('blah, debhelper (= 8)', 'debhelper', '9'))
        self.assertEqual(
            'blah, debhelper (= 9)',
            ensure_exact_version('blah, debhelper (= 10)', 'debhelper', '9'))


class DropDependencyTests(TestCase):

    def test_deleted(self):
        self.assertEqual(
            'debhelper (>= 9)',
            drop_dependency('debhelper (>= 9), dh-autoreconf',
                            'dh-autoreconf'))
        self.assertEqual(
            'dh-autoreconf',
            drop_dependency('debhelper (>= 9), dh-autoreconf', 'debhelper'))
        self.assertEqual(
            '', drop_dependency('debhelper (>= 9)', 'debhelper'))
        self.assertEqual(
            'debhelper-compat (= 12)',
            drop_dependency(
                'debhelper (>= 9), debhelper-compat (= 12)',
                'debhelper'))


class AddDependencyTests(TestCase):

    def test_added(self):
        self.assertEqual(
            'debhelper (>= 9), dh-autoreconf',
            add_dependency('debhelper (>= 9)', 'dh-autoreconf'))
        self.assertEqual(
            'debhelper (>= 9), ${misc:Depends}',
            add_dependency('debhelper (>= 9)', '${misc:Depends}'))
        self.assertEqual(
            'debhelper (>= 9), blah,',
            add_dependency('debhelper (>= 9),', 'blah'))

    def test_indentation(self):
        self.assertEqual("""foo,
    bar,
    blah""", add_dependency("""foo,
    bar""", 'blah'))
        self.assertEqual("""foo,
 bar,
 blah""", add_dependency("""foo,
 bar""", 'blah'))
        self.assertEqual("""foo,
 bar,
 blah""", add_dependency("""foo,
 bar
""", 'blah'))

    def test_insert(self):
        self.assertEqual("""blah,
    foo,
    bar""", add_dependency("""foo,
    bar""", 'blah', position=0))
        self.assertEqual("""foo,
    blah,
    bar""", add_dependency("""foo,
    bar""", 'blah', position=1))

    def test_odd_syntax(self):
        self.assertEqual("""
 foo
 , bar
 , blah""", add_dependency("""
 foo
 , bar
""", 'blah'))
        self.assertEqual("""
 foo
 , blah
 , bar""", add_dependency("""
 foo
 , bar
""", 'blah', position=1))


class GetRelationTests(TestCase):

    def test_missing(self):
        self.assertRaises(
            KeyError, get_relation, '', 'debhelper')
        self.assertRaises(
            KeyError,
            get_relation, 'blah', 'debhelper')

    def test_simple(self):
        self.assertEqual(
            (0, [PkgRelation('debhelper', ('>=', '9'))]),
            get_relation(
                'debhelper (>= 9)', 'debhelper'))
        self.assertEqual(
            (1, [PkgRelation('debhelper', ('=', '9'))]),
            get_relation(
                'blah, debhelper (= 9)', 'debhelper'))

    def test_complex(self):
        self.assertRaises(
            ValueError,
            get_relation, 'blah | debhelper (= 9)', 'debhelper')
        self.assertRaises(
            ValueError,
            get_relation,
            'blah, debhelper (= 9) | debhelper (<< 10)', 'debhelper')


class IterRelationsTests(TestCase):

    def test_missing(self):
        self.assertEqual(
            [], list(iter_relations('', 'debhelper')))
        self.assertEqual(
            [], list(iter_relations('blah', 'debhelper')))

    def test_simple(self):
        self.assertEqual(
            [(0, [PkgRelation('debhelper', ('>=', '9'))])],
            list(iter_relations(
                'debhelper (>= 9)', 'debhelper')))
        self.assertEqual(
            [(1, [PkgRelation('debhelper', ('=', '9'))])],
            list(iter_relations(
                'blah, debhelper (= 9)', 'debhelper')))

    def test_complex(self):
        self.assertEqual(
            [(0, [PkgRelation('blah'), PkgRelation('debhelper', ('=', '9'))])],
            list(iter_relations('blah | debhelper (= 9)', 'debhelper')))
        self.assertEqual(
            [(1,
              [PkgRelation('debhelper', ('=', '9')),
               PkgRelation('debhelper', ('<<', '10'))])],
            list(iter_relations(
                'blah, debhelper (= 9) | debhelper (<< 10)', 'debhelper')))


class DeleteFromListTests(TestCase):

    def test_intermediate(self):
        self.assertEqual('a, c', delete_from_list('a, b, c', 'b'))
        self.assertEqual('a, c', delete_from_list('a, b, c', 'b '))

    def test_head(self):
        self.assertEqual('b, c', delete_from_list('a, b, c', 'a'))
        self.assertEqual(' b, c', delete_from_list(' a, b, c', 'a'))

    def test_tail(self):
        self.assertEqual('a, b', delete_from_list('a, b, c', 'c'))
        self.assertEqual('a, b', delete_from_list('a, b , c', 'c'))

    def test_only(self):
        self.assertEqual('a', delete_from_list('a', 'c'))
        self.assertEqual('', delete_from_list('a', 'a'))


class IsDepImpliedTests(TestCase):

    def parse(self, p):
        [dep] = PkgRelation.parse(p)
        return dep

    def test_no_version(self):
        self.assertTrue(
            is_dep_implied(self.parse('bzr'), self.parse('bzr')))
        self.assertTrue(
            is_dep_implied(self.parse('bzr'), self.parse('bzr (>= 3)')))
        self.assertTrue(
            is_dep_implied(self.parse('bzr'), self.parse('bzr (<< 3)')))

    def test_wrong_package(self):
        self.assertFalse(
            is_dep_implied(self.parse('bzr'), self.parse('foo (<< 3)')))

    def test_version(self):
        self.assertFalse(
            is_dep_implied(self.parse('bzr (>= 3)'), self.parse('bzr (<< 3)')))
        self.assertTrue(
            is_dep_implied(self.parse('bzr (>= 3)'), self.parse('bzr (= 3)')))
        self.assertFalse(
            is_dep_implied(self.parse('bzr (= 3)'), self.parse('bzr (>= 3)')))
        self.assertFalse(
            is_dep_implied(self.parse('bzr (>= 3)'), self.parse('bzr (>> 3)')))
        self.assertFalse(
            is_dep_implied(self.parse('bzr (= 3)'), self.parse('bzr (= 4)')))
        self.assertFalse(
            is_dep_implied(self.parse('bzr (>= 3)'), self.parse('bzr (>= 2)')))
        self.assertTrue(
            is_dep_implied(self.parse('bzr (>= 3)'), self.parse('bzr (>= 3)')))
        self.assertTrue(
            is_dep_implied(self.parse('bzr'), self.parse('bzr (<< 3)')))
        self.assertTrue(
            is_dep_implied(self.parse('bzr (<< 3)'), self.parse('bzr (<< 3)')))
        self.assertTrue(
            is_dep_implied(self.parse('bzr (<= 3)'), self.parse('bzr (<< 3)')))
        self.assertFalse(
            is_dep_implied(self.parse('bzr (>= 2)'), self.parse('bzr (<< 3)')))
        self.assertFalse(
            is_dep_implied(self.parse('bzr (<< 2)'), self.parse('bzr (<< 3)')))
        self.assertFalse(
            is_dep_implied(self.parse('bzr (<= 2)'), self.parse('bzr (<< 3)')))
        self.assertTrue(
            is_dep_implied(self.parse('bzr (<= 5)'), self.parse('bzr (<< 3)')))
        self.assertTrue(
            is_dep_implied(self.parse('bzr (<= 5)'), self.parse('bzr (= 3)')))
        self.assertFalse(
            is_dep_implied(self.parse('bzr (<= 5)'), self.parse('bzr (>= 3)')))
        self.assertTrue(
            is_dep_implied(self.parse('bzr (>> 5)'), self.parse('bzr (>> 6)')))
        self.assertTrue(
            is_dep_implied(self.parse('bzr (>> 5)'), self.parse('bzr (>> 5)')))
        self.assertFalse(
            is_dep_implied(self.parse('bzr (>> 5)'), self.parse('bzr (>> 4)')))
        self.assertTrue(
            is_dep_implied(self.parse('bzr (>> 5)'), self.parse('bzr (= 6)')))
        self.assertFalse(
            is_dep_implied(self.parse('bzr (>> 5)'), self.parse('bzr (= 5)')))


class IsRelationImpliedTests(TestCase):

    def test_unrelated(self):
        self.assertFalse(is_relation_implied('bzr', 'bar'))
        self.assertFalse(is_relation_implied('bzr (= 3)', 'bar'))
        self.assertFalse(is_relation_implied('bzr (= 3) | foo', 'bar'))

    def test_too_old(self):
        self.assertFalse(is_relation_implied('bzr (= 3)', 'bzr'))
        self.assertFalse(is_relation_implied('bzr (= 3)', 'bzr (= 2)'))
        self.assertFalse(is_relation_implied('bzr (= 3)', 'bzr (>= 2)'))

    def test_ors(self):
        self.assertFalse(is_relation_implied('bzr (= 3)', 'bzr | foo'))
        self.assertFalse(is_relation_implied('bzr', 'bzr | foo'))
        self.assertTrue(is_relation_implied('bzr | foo', 'bzr | foo'))

    def test_implied(self):
        self.assertTrue(is_relation_implied('bzr (= 3)', 'bzr (= 3)'))
        self.assertTrue(is_relation_implied('bzr (>= 3)', 'bzr (>= 4)'))
        self.assertTrue(is_relation_implied('bzr (>= 4)', 'bzr (>= 4)'))
        self.assertTrue(is_relation_implied('bzr', 'bzr'))
        self.assertTrue(is_relation_implied('bzr | foo', 'bzr'))
        self.assertFalse(is_relation_implied('bzr (= 3)', 'bzr (>= 3)'))


class CdbsResolverConflictTests(TestCase):

    def test_build_depends(self):
        val = _cdbs_resolve_conflict(
            ('Source', 'libnetsds-perl'), 'Build-Depends',
            'debhelper (>= 6), foo', '@cdbs@', 'debhelper (>= 10), foo')
        self.assertEqual(val, '@cdbs@, debhelper (>= 10)')
        val = _cdbs_resolve_conflict(
            ('Source', 'libnetsds-perl'), 'Build-Depends',
            'debhelper (>= 6), foo',  '@cdbs@, foo',
            'debhelper (>= 10), foo')
        self.assertEqual(val, '@cdbs@, foo, debhelper (>= 10)')
        val = _cdbs_resolve_conflict(
            ('Source', 'libnetsds-perl'), 'Build-Depends',
            'debhelper (>= 6), foo', '@cdbs@, debhelper (>= 9)',
            'debhelper (>= 10), foo')
        self.assertEqual(val, '@cdbs@, debhelper (>= 10)')


class ParseStandardsVersionTests(TestCase):

    def test_parse(self):
        self.assertEqual((4, 5, 0), parse_standards_version('4.5.0'))
