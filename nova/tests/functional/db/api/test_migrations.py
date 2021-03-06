#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Tests for database migrations.
There are "opportunistic" tests which allows testing against all 3 databases
(sqlite in memory, mysql, pg) in a properly configured unit test environment.

For the opportunistic testing you need to set up db's named 'openstack_citest'
with user 'openstack_citest' and password 'openstack_citest' on localhost. The
test will then use that db and u/p combo to run the tests.

For postgres on Ubuntu this can be done with the following commands::

| sudo -u postgres psql
| postgres=# create user openstack_citest with createdb login password
|       'openstack_citest';
| postgres=# create database openstack_citest with owner openstack_citest;

"""

import os

from migrate.versioning import repository
import mock
from oslo_db.sqlalchemy import enginefacade
from oslo_db.sqlalchemy import test_fixtures
from oslo_db.sqlalchemy import test_migrations
from oslo_db.sqlalchemy import utils as db_utils
from oslo_serialization import jsonutils
import sqlalchemy
from sqlalchemy.engine import reflection
import testtools

from nova.db import migration
from nova.db.sqlalchemy.api_migrations import migrate_repo
from nova.db.sqlalchemy import api_models
from nova.db.sqlalchemy import migration as sa_migration
from nova import test
from nova.test import uuids
from nova.tests import fixtures as nova_fixtures


class NovaAPIModelsSync(test_migrations.ModelsMigrationsSync):
    """Test that the models match the database after migrations are run."""

    def setUp(self):
        super(NovaAPIModelsSync, self).setUp()
        self.engine = enginefacade.writer.get_engine()

    def db_sync(self, engine):
        with mock.patch.object(sa_migration, 'get_engine',
                               return_value=engine):
            sa_migration.db_sync(database='api')

    @property
    def migrate_engine(self):
        return self.engine

    def get_engine(self, context=None):
        return self.migrate_engine

    def get_metadata(self):
        return api_models.API_BASE.metadata

    def include_object(self, object_, name, type_, reflected, compare_to):
        if type_ == 'table':
            # migrate_version is a sqlalchemy-migrate control table and
            # isn't included in the model.
            if name == 'migrate_version':
                return False

        return True

    def filter_metadata_diff(self, diff):
        # Filter out diffs that shouldn't cause a sync failure.

        new_diff = []

        # Define a whitelist of ForeignKeys that exist on the model but not in
        # the database. They will be removed from the model at a later time.
        fkey_whitelist = {'build_requests': ['request_spec_id']}

        # Define a whitelist of columns that will be removed from the
        # DB at a later release and aren't on a model anymore.

        column_whitelist = {
                'build_requests': ['vm_state', 'instance_metadata',
                    'display_name', 'access_ip_v6', 'access_ip_v4', 'key_name',
                    'locked_by', 'image_ref', 'progress', 'request_spec_id',
                    'info_cache', 'user_id', 'task_state', 'security_groups',
                    'config_drive'],
                'resource_providers': ['can_host'],
        }

        for element in diff:
            if isinstance(element, list):
                # modify_nullable is a list
                new_diff.append(element)
            else:
                # tuple with action as first element. Different actions have
                # different tuple structures.
                if element[0] == 'add_fk':
                    fkey = element[1]
                    tablename = fkey.table.name
                    column_keys = fkey.column_keys
                    if (tablename in fkey_whitelist and
                            column_keys == fkey_whitelist[tablename]):
                        continue
                elif element[0] == 'remove_column':
                    tablename = element[2]
                    column = element[3]
                    if (tablename in column_whitelist and
                            column.name in column_whitelist[tablename]):
                        continue

                new_diff.append(element)
        return new_diff


class TestNovaAPIMigrationsSQLite(NovaAPIModelsSync,
                                  test_fixtures.OpportunisticDBTestMixin,
                                  testtools.TestCase):
    pass


class TestNovaAPIMigrationsMySQL(NovaAPIModelsSync,
                                 test_fixtures.OpportunisticDBTestMixin,
                                 testtools.TestCase):
    FIXTURE = test_fixtures.MySQLOpportunisticFixture


class TestNovaAPIMigrationsPostgreSQL(NovaAPIModelsSync,
        test_fixtures.OpportunisticDBTestMixin, testtools.TestCase):
    FIXTURE = test_fixtures.PostgresqlOpportunisticFixture


class NovaAPIMigrationsWalk(test_migrations.WalkVersionsMixin):
    def setUp(self):
        # NOTE(sdague): the oslo_db base test case completely
        # invalidates our logging setup, we actually have to do that
        # before it is called to keep this from vomiting all over our
        # test output.
        self.useFixture(nova_fixtures.StandardLogging())
        super(NovaAPIMigrationsWalk, self).setUp()
        self.engine = enginefacade.writer.get_engine()

    @property
    def INIT_VERSION(self):
        return migration.db_initial_version('api')

    @property
    def REPOSITORY(self):
        return repository.Repository(
            os.path.abspath(os.path.dirname(migrate_repo.__file__)))

    @property
    def migration_api(self):
        return sa_migration.versioning_api

    @property
    def migrate_engine(self):
        return self.engine

    def _skippable_migrations(self):
        newton_placeholders = list(range(21, 26))
        ocata_placeholders = list(range(31, 41))
        pike_placeholders = list(range(45, 50))
        queens_placeholders = list(range(53, 58))
        # We forgot to add the rocky placeholders
        stein_placeholders = list(range(63, 68))
        train_placeholders = list(range(68, 73))
        ussuri_placeholders = list(range(73, 78))
        victoria_placeholders = list(range(78, 83))
        special_cases = [
            self.INIT_VERSION + 1,  # initial change
            30,  # Enforcement migration, no changes to test
        ]
        return (newton_placeholders +
                ocata_placeholders +
                pike_placeholders +
                queens_placeholders +
                stein_placeholders +
                train_placeholders +
                ussuri_placeholders +
                victoria_placeholders +
                special_cases)

    def migrate_up(self, version, with_data=False):
        if with_data:
            check = getattr(self, '_check_%03d' % version, None)
            if version not in self._skippable_migrations():
                self.assertIsNotNone(check,
                                     ('API DB Migration %i does not have a '
                                      'test. Please add one!') % version)
        super(NovaAPIMigrationsWalk, self).migrate_up(version, with_data)

    def test_walk_versions(self):
        self.walk_versions(snake_walk=False, downgrade=False)

    def assertColumnExists(self, engine, table_name, column):
        self.assertTrue(db_utils.column_exists(engine, table_name, column),
                'Column %s.%s does not exist' % (table_name, column))

    def assertIndexExists(self, engine, table_name, index):
        self.assertTrue(db_utils.index_exists(engine, table_name, index),
                        'Index %s on table %s does not exist' %
                        (index, table_name))

    def assertUniqueConstraintExists(self, engine, table_name, columns):
        inspector = reflection.Inspector.from_engine(engine)
        constrs = inspector.get_unique_constraints(table_name)
        constr_columns = [constr['column_names'] for constr in constrs]
        self.assertIn(columns, constr_columns)

    def assertTableNotExists(self, engine, table_name):
        self.assertRaises(sqlalchemy.exc.NoSuchTableError,
                db_utils.get_table, engine, table_name)

    def _check_026(self, engine, data):
        self.assertColumnExists(engine, 'resource_classes', 'id')
        self.assertColumnExists(engine, 'resource_classes', 'name')

    def _check_027(self, engine, data):
        # quota_classes
        for column in ['created_at',
                       'updated_at',
                       'id',
                       'class_name',
                       'resource',
                       'hard_limit']:
            self.assertColumnExists(engine, 'quota_classes', column)

        self.assertIndexExists(engine, 'quota_classes',
            'quota_classes_class_name_idx')

        # quota_usages
        for column in ['created_at',
                       'updated_at',
                       'id',
                       'project_id',
                       'resource',
                       'in_use',
                       'reserved',
                       'until_refresh',
                       'user_id']:
            self.assertColumnExists(engine, 'quota_usages', column)

        self.assertIndexExists(engine, 'quota_usages',
            'quota_usages_project_id_idx')
        self.assertIndexExists(engine, 'quota_usages',
            'quota_usages_user_id_idx')

        # quotas
        for column in ['created_at',
                       'updated_at',
                       'id',
                       'project_id',
                       'resource',
                       'hard_limit']:
            self.assertColumnExists(engine, 'quotas', column)

        self.assertUniqueConstraintExists(engine, 'quotas',
                                        ['project_id', 'resource'])

        # project_user_quotas
        for column in ['created_at',
                       'updated_at',
                       'id',
                       'user_id',
                       'project_id',
                       'resource',
                       'hard_limit']:
            self.assertColumnExists(engine, 'project_user_quotas', column)

        self.assertUniqueConstraintExists(engine, 'project_user_quotas',
                                        ['user_id', 'project_id', 'resource'])
        self.assertIndexExists(engine, 'project_user_quotas',
            'project_user_quotas_project_id_idx')
        self.assertIndexExists(engine, 'project_user_quotas',
            'project_user_quotas_user_id_idx')

        # reservations
        for column in ['created_at',
                       'updated_at',
                       'id',
                       'uuid',
                       'usage_id',
                       'project_id',
                       'resource',
                       'delta',
                       'expire',
                       'user_id']:
            self.assertColumnExists(engine, 'reservations', column)

        self.assertIndexExists(engine, 'reservations',
                                       'reservations_project_id_idx')
        self.assertIndexExists(engine, 'reservations',
                                       'reservations_uuid_idx')
        self.assertIndexExists(engine, 'reservations',
                                       'reservations_expire_idx')
        self.assertIndexExists(engine, 'reservations',
                                       'reservations_user_id_idx')
        # Ensure the foreign key still exists
        inspector = reflection.Inspector.from_engine(engine)
        # There should only be one foreign key here
        fk = inspector.get_foreign_keys('reservations')[0]
        self.assertEqual('quota_usages', fk['referred_table'])
        self.assertEqual(['id'], fk['referred_columns'])

    def _pre_upgrade_028(self, engine):
        build_requests = db_utils.get_table(engine, 'build_requests')
        fake_build_req = {'id': 2021,
                          'project_id': 'fake_proj_id',
                          'instance': '{"uuid": "foo", "name": "bar"}'}
        build_requests.insert().execute(fake_build_req)

    def _check_028(self, engine, data):
        build_requests = db_utils.get_table(engine, 'build_requests')
        if engine.name == 'mysql':
            self.assertIsInstance(build_requests.c.block_device_mappings.type,
                                  sqlalchemy.dialects.mysql.MEDIUMTEXT)

        fake_build_req = build_requests.select(
            build_requests.c.id == 2021).execute().first()
        self.assertEqual('{"uuid": "foo", "name": "bar"}',
                         fake_build_req.instance)

    def _check_029(self, engine, data):
        for column in ['created_at', 'updated_at', 'id', 'uuid']:
            self.assertColumnExists(engine, 'placement_aggregates', column)

    def _check_041(self, engine, data):
        self.assertColumnExists(engine, 'traits', 'id')
        self.assertUniqueConstraintExists(engine, 'traits', ['name'])

        self.assertColumnExists(engine, 'resource_provider_traits', 'trait_id')
        self.assertColumnExists(engine, 'resource_provider_traits',
                                'resource_provider_id')
        self.assertIndexExists(
            engine, 'resource_provider_traits',
            'resource_provider_traits_resource_provider_trait_idx')

        inspector = reflection.Inspector.from_engine(engine)
        self.assertEqual(
            2, len(inspector.get_foreign_keys('resource_provider_traits')))
        for fk in inspector.get_foreign_keys('resource_provider_traits'):
            if 'traits' == fk['referred_table']:
                self.assertEqual(['id'], fk['referred_columns'])
                self.assertEqual(['trait_id'], fk['constrained_columns'])
            elif 'resource_providers' == fk['referred_table']:
                self.assertEqual(['id'], fk['referred_columns'])
                self.assertEqual(['resource_provider_id'],
                                 fk['constrained_columns'])

    def _check_042(self, engine, data):
        self.assertColumnExists(engine, 'build_requests', 'tags')

    def _check_043(self, engine, data):
        for column in ['created_at', 'updated_at', 'id', 'uuid', 'project_id',
                       'user_id']:
            self.assertColumnExists(engine, 'consumers', column)

        self.assertIndexExists(engine, 'consumers',
                               'consumers_project_id_uuid_idx')
        self.assertIndexExists(engine, 'consumers',
                               'consumers_project_id_user_id_uuid_idx')
        self.assertUniqueConstraintExists(engine, 'consumers', ['uuid'])

    def _check_044(self, engine, data):
        for column in ['created_at', 'updated_at', 'id', 'external_id']:
            self.assertColumnExists(engine, 'projects', column)
            self.assertColumnExists(engine, 'users', column)

        self.assertUniqueConstraintExists(engine, 'projects', ['external_id'])
        self.assertUniqueConstraintExists(engine, 'users', ['external_id'])

        # We needed to drop and recreate columns and indexes on consumers, so
        # check that worked out properly
        self.assertColumnExists(engine, 'consumers', 'project_id')
        self.assertColumnExists(engine, 'consumers', 'user_id')
        self.assertIndexExists(
            engine, 'consumers',
            'consumers_project_id_uuid_idx',
        )
        self.assertIndexExists(
            engine, 'consumers',
            'consumers_project_id_user_id_uuid_idx',
        )

    def _check_050(self, engine, data):
        self.assertColumnExists(engine, 'flavors', 'description')

    def _check_051(self, engine, data):
        for column in ['root_provider_id', 'parent_provider_id']:
            self.assertColumnExists(engine, 'resource_providers', column)
        self.assertIndexExists(engine, 'resource_providers',
            'resource_providers_root_provider_id_idx')
        self.assertIndexExists(engine, 'resource_providers',
            'resource_providers_parent_provider_id_idx')

    def _pre_upgrade_052(self, engine):
        request_specs = db_utils.get_table(engine, 'request_specs')
        # The spec value is a serialized json blob.
        spec = jsonutils.dumps(
            {"instance_group": {"id": 42,
                                "members": ["uuid1",
                                            "uuid2",
                                            "uuid3"]}})
        fake_request_spec = {
            'id': 42, 'spec': spec, 'instance_uuid': uuids.instance}
        request_specs.insert().execute(fake_request_spec)

    def _check_052(self, engine, data):
        request_specs = db_utils.get_table(engine, 'request_specs')
        if engine.name == 'mysql':
            self.assertIsInstance(request_specs.c.spec.type,
                                  sqlalchemy.dialects.mysql.MEDIUMTEXT)

        expected_spec = {"instance_group": {"id": 42,
                                            "members": ["uuid1",
                                                        "uuid2",
                                                        "uuid3"]}}
        from_db_request_spec = request_specs.select(
            request_specs.c.id == 42).execute().first()
        self.assertEqual(uuids.instance, from_db_request_spec['instance_uuid'])
        db_spec = jsonutils.loads(from_db_request_spec['spec'])
        self.assertDictEqual(expected_spec, db_spec)

    def _check_058(self, engine, data):
        self.assertColumnExists(engine, 'cell_mappings', 'disabled')

    def _pre_upgrade_059(self, engine):
        # Add a fake consumers table record to verify that generation is
        # added with a default value of 0.
        projects = db_utils.get_table(engine, 'projects')
        project_id = projects.insert().execute(
            dict(external_id=uuids.project_external_id)
        ).inserted_primary_key[0]
        users = db_utils.get_table(engine, 'users')
        user_id = users.insert().execute(
            dict(external_id=uuids.user_external_id)
        ).inserted_primary_key[0]
        consumers = db_utils.get_table(engine, 'consumers')
        fake_consumer = dict(
            uuid=uuids.consumer_uuid, project_id=project_id, user_id=user_id)
        consumers.insert().execute(fake_consumer)

    def _check_059(self, engine, data):
        self.assertColumnExists(engine, "consumers", "generation")
        # Assert we have one existing entry and it's generation value is 0.
        consumers = db_utils.get_table(engine, 'consumers')
        result = consumers.select().execute().fetchall()
        self.assertEqual(1, len(result))
        self.assertEqual(0, result[0]['generation'])

    def _check_060(self, engine, data):
        self.assertColumnExists(engine, 'instance_group_policy', 'rules')

    def _check_061(self, engine, data):
        self.assertColumnExists(engine, 'instance_mappings',
            'queued_for_delete')

    def _check_062(self, engine, data):
        self.assertColumnExists(engine, 'instance_mappings', 'user_id')
        self.assertIndexExists(engine, 'instance_mappings',
                               'instance_mappings_user_id_project_id_idx')


class TestNovaAPIMigrationsWalkSQLite(NovaAPIMigrationsWalk,
                                      test_fixtures.OpportunisticDBTestMixin,
                                      test.NoDBTestCase):
    pass


class TestNovaAPIMigrationsWalkMySQL(NovaAPIMigrationsWalk,
                                     test_fixtures.OpportunisticDBTestMixin,
                                     test.NoDBTestCase):
    FIXTURE = test_fixtures.MySQLOpportunisticFixture


class TestNovaAPIMigrationsWalkPostgreSQL(NovaAPIMigrationsWalk,
        test_fixtures.OpportunisticDBTestMixin, test.NoDBTestCase):
    FIXTURE = test_fixtures.PostgresqlOpportunisticFixture
