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

from migrate.changeset.constraint import ForeignKeyConstraint
from migrate import UniqueConstraint
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import dialects
from sqlalchemy import Enum
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import MetaData
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import Text
from sqlalchemy import Unicode

from nova.db.sqlalchemy.api_models import MediumText
from nova.objects import keypair


def InetSmall():
    return String(length=39).with_variant(
        dialects.postgresql.INET(), 'postgresql'
    )


def upgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine

    cell_mappings = Table('cell_mappings', meta,
        Column('created_at', DateTime),
        Column('updated_at', DateTime),
        Column('id', Integer, primary_key=True, nullable=False),
        Column('uuid', String(length=36), nullable=False),
        Column('name', String(length=255)),
        Column('transport_url', Text()),
        Column('database_connection', Text()),
        UniqueConstraint('uuid', name='uniq_cell_mappings0uuid'),
        Index('uuid_idx', 'uuid'),
        mysql_engine='InnoDB',
        mysql_charset='utf8'
    )

    host_mappings = Table('host_mappings', meta,
        Column('created_at', DateTime),
        Column('updated_at', DateTime),
        Column('id', Integer, primary_key=True, nullable=False),
        Column('cell_id', Integer, nullable=False),
        Column('host', String(length=255), nullable=False),
        UniqueConstraint(
            'host', name='uniq_host_mappings0host'),
        Index('host_idx', 'host'),
        ForeignKeyConstraint(
            columns=['cell_id'], refcolumns=[cell_mappings.c.id]),
        mysql_engine='InnoDB',
        mysql_charset='utf8'
    )

    instance_mappings = Table('instance_mappings', meta,
        Column('created_at', DateTime),
        Column('updated_at', DateTime),
        Column('id', Integer, primary_key=True, nullable=False),
        Column('instance_uuid', String(length=36), nullable=False),
        Column('cell_id', Integer, nullable=True),
        Column('project_id', String(length=255), nullable=False),
        UniqueConstraint(
            'instance_uuid', name='uniq_instance_mappings0instance_uuid'),
        Index('instance_uuid_idx', 'instance_uuid'),
        Index('project_id_idx', 'project_id'),
        ForeignKeyConstraint(
            columns=['cell_id'], refcolumns=[cell_mappings.c.id]),
        mysql_engine='InnoDB',
        mysql_charset='utf8'
    )

    flavors = Table('flavors', meta,
        Column('created_at', DateTime),
        Column('updated_at', DateTime),
        Column('name', String(length=255), nullable=False),
        Column('id', Integer, primary_key=True, nullable=False),
        Column('memory_mb', Integer, nullable=False),
        Column('vcpus', Integer, nullable=False),
        Column('swap', Integer, nullable=False),
        Column('vcpu_weight', Integer),
        Column('flavorid', String(length=255), nullable=False),
        Column('rxtx_factor', Float),
        Column('root_gb', Integer),
        Column('ephemeral_gb', Integer),
        Column('disabled', Boolean),
        Column('is_public', Boolean),
        UniqueConstraint('flavorid', name='uniq_flavors0flavorid'),
        UniqueConstraint('name', name='uniq_flavors0name'),
        mysql_engine='InnoDB',
        mysql_charset='utf8'
    )

    flavor_extra_specs = Table('flavor_extra_specs', meta,
        Column('created_at', DateTime),
        Column('updated_at', DateTime),
        Column('id', Integer, primary_key=True, nullable=False),
        Column('flavor_id', Integer, nullable=False),
        Column('key', String(length=255), nullable=False),
        Column('value', String(length=255)),
        UniqueConstraint(
            'flavor_id', 'key', name='uniq_flavor_extra_specs0flavor_id0key'),
        Index('flavor_extra_specs_flavor_id_key_idx', 'flavor_id', 'key'),
        ForeignKeyConstraint(columns=['flavor_id'], refcolumns=[flavors.c.id]),
        mysql_engine='InnoDB',
        mysql_charset='utf8'
    )

    flavor_projects = Table('flavor_projects', meta,
        Column('created_at', DateTime),
        Column('updated_at', DateTime),
        Column('id', Integer, primary_key=True, nullable=False),
        Column('flavor_id', Integer, nullable=False),
        Column('project_id', String(length=255), nullable=False),
        UniqueConstraint(
            'flavor_id', 'project_id',
            name='uniq_flavor_projects0flavor_id0project_id'),
        ForeignKeyConstraint(
            columns=['flavor_id'], refcolumns=[flavors.c.id]),
        mysql_engine='InnoDB',
        mysql_charset='utf8'
    )

    request_specs = Table('request_specs', meta,
        Column('created_at', DateTime),
        Column('updated_at', DateTime),
        Column('id', Integer, primary_key=True, nullable=False),
        Column('instance_uuid', String(36), nullable=False),
        Column('spec', Text, nullable=False),
        UniqueConstraint(
            'instance_uuid', name='uniq_request_specs0instance_uuid'),
        Index('request_spec_instance_uuid_idx', 'instance_uuid'),
        mysql_engine='InnoDB',
        mysql_charset='utf8'
    )

    build_requests = Table('build_requests', meta,
        Column('created_at', DateTime),
        Column('updated_at', DateTime),
        Column('id', Integer, primary_key=True, nullable=False),
        Column('request_spec_id', Integer, nullable=True),
        Column('project_id', String(length=255), nullable=False),
        Column('user_id', String(length=255), nullable=True),
        Column('display_name', String(length=255)),
        Column('instance_metadata', Text),
        Column('progress', Integer),
        Column('vm_state', String(length=255)),
        Column('task_state', String(length=255)),
        Column('image_ref', String(length=255)),
        Column('access_ip_v4', InetSmall()),
        Column('access_ip_v6', InetSmall()),
        Column('info_cache', Text),
        Column('security_groups', Text, nullable=True),
        Column('config_drive', Boolean, default=False, nullable=True),
        Column('key_name', String(length=255)),
        Column(
            'locked_by',
            Enum('owner', 'admin', name='build_requests0locked_by')),
        Column('instance_uuid', String(length=36)),
        Column('instance', Text()),
        Column('block_device_mappings', MediumText()),
        UniqueConstraint(
            'instance_uuid', name='uniq_build_requests0instance_uuid'),
        Index('build_requests_project_id_idx', 'project_id'),
        Index('build_requests_instance_uuid_idx', 'instance_uuid'),
        mysql_engine='InnoDB',
        mysql_charset='utf8'
    )

    keypairs = Table('key_pairs', meta,
        Column('created_at', DateTime),
        Column('updated_at', DateTime),
        Column('id', Integer, primary_key=True, nullable=False),
        Column('name', String(255), nullable=False),
        Column('user_id', String(255), nullable=False),
        Column('fingerprint', String(255)),
        Column('public_key', Text()),
        Column(
            'type', Enum('ssh', 'x509', metadata=meta, name='keypair_types'),
            nullable=False, server_default=keypair.KEYPAIR_TYPE_SSH),
        UniqueConstraint(
            'user_id', 'name', name='uniq_key_pairs0user_id0name'),
        mysql_engine='InnoDB',
        mysql_charset='utf8'
    )

    nameargs = {}
    if migrate_engine.name == 'mysql':
        nameargs['collation'] = 'utf8_bin'

    resource_providers = Table(
        'resource_providers', meta,
        Column('created_at', DateTime),
        Column('updated_at', DateTime),
        Column('id', Integer, primary_key=True, nullable=False),
        Column('uuid', String(36), nullable=False),
        Column('name', Unicode(200, **nameargs), nullable=True),
        Column('generation', Integer, default=0),
        Column('can_host', Integer, default=0),
        UniqueConstraint('uuid', name='uniq_resource_providers0uuid'),
        UniqueConstraint('name', name='uniq_resource_providers0name'),
        Index('resource_providers_name_idx', 'name'),
        Index('resource_providers_uuid_idx', 'uuid'),
        mysql_engine='InnoDB',
        mysql_charset='latin1'
    )

    inventories = Table(
        'inventories', meta,
        Column('created_at', DateTime),
        Column('updated_at', DateTime),
        Column('id', Integer, primary_key=True, nullable=False),
        Column('resource_provider_id', Integer, nullable=False),
        Column('resource_class_id', Integer, nullable=False),
        Column('total', Integer, nullable=False),
        Column('reserved', Integer, nullable=False),
        Column('min_unit', Integer, nullable=False),
        Column('max_unit', Integer, nullable=False),
        Column('step_size', Integer, nullable=False),
        Column('allocation_ratio', Float, nullable=False),
        Index(
            'inventories_resource_provider_id_idx', 'resource_provider_id'),
        Index(
            'inventories_resource_provider_resource_class_idx',
            'resource_provider_id', 'resource_class_id'),
        Index(
            'inventories_resource_class_id_idx', 'resource_class_id'),
        UniqueConstraint(
            'resource_provider_id', 'resource_class_id',
            name='uniq_inventories0resource_provider_resource_class'),
        mysql_engine='InnoDB',
        mysql_charset='latin1'
    )

    allocations = Table(
        'allocations', meta,
        Column('created_at', DateTime),
        Column('updated_at', DateTime),
        Column('id', Integer, primary_key=True, nullable=False),
        Column('resource_provider_id', Integer, nullable=False),
        Column('consumer_id', String(36), nullable=False),
        Column('resource_class_id', Integer, nullable=False),
        Column('used', Integer, nullable=False),
        Index(
            'allocations_resource_provider_class_used_idx',
            'resource_provider_id', 'resource_class_id', 'used'),
        Index(
            'allocations_resource_class_id_idx', 'resource_class_id'),
        Index('allocations_consumer_id_idx', 'consumer_id'),
        mysql_engine='InnoDB',
        mysql_charset='latin1'
    )

    resource_provider_aggregates = Table(
        'resource_provider_aggregates', meta,
        Column('created_at', DateTime),
        Column('updated_at', DateTime),
        Column(
            'resource_provider_id', Integer, primary_key=True, nullable=False),
        Column('aggregate_id', Integer, primary_key=True, nullable=False),
        Index(
            'resource_provider_aggregates_aggregate_id_idx', 'aggregate_id'),
        mysql_engine='InnoDB',
        mysql_charset='latin1'
    )

    aggregates = Table('aggregates', meta,
        Column('created_at', DateTime),
        Column('updated_at', DateTime),
        Column('id', Integer, primary_key=True, nullable=False),
        Column('uuid', String(length=36)),
        Column('name', String(length=255)),
        Index('aggregate_uuid_idx', 'uuid'),
        UniqueConstraint('name', name='uniq_aggregate0name'),
        mysql_engine='InnoDB',
        mysql_charset='utf8'
    )

    aggregate_hosts = Table('aggregate_hosts', meta,
        Column('created_at', DateTime),
        Column('updated_at', DateTime),
        Column('id', Integer, primary_key=True, nullable=False),
        Column('host', String(length=255)),
        Column(
            'aggregate_id', Integer, ForeignKey('aggregates.id'),
            nullable=False),
        UniqueConstraint(
            'host', 'aggregate_id',
            name='uniq_aggregate_hosts0host0aggregate_id'),
        mysql_engine='InnoDB',
        mysql_charset='utf8'
    )

    aggregate_metadata = Table('aggregate_metadata', meta,
        Column('created_at', DateTime),
        Column('updated_at', DateTime),
        Column('id', Integer, primary_key=True, nullable=False),
        Column(
            'aggregate_id', Integer, ForeignKey('aggregates.id'),
            nullable=False),
        Column('key', String(length=255), nullable=False),
        Column('value', String(length=255), nullable=False),
        UniqueConstraint(
            'aggregate_id', 'key',
            name='uniq_aggregate_metadata0aggregate_id0key'),
        Index('aggregate_metadata_key_idx', 'key'),
        mysql_engine='InnoDB',
        mysql_charset='utf8'
    )

    groups = Table('instance_groups', meta,
        Column('created_at', DateTime),
        Column('updated_at', DateTime),
        Column('id', Integer, primary_key=True, nullable=False),
        Column('user_id', String(length=255)),
        Column('project_id', String(length=255)),
        Column('uuid', String(length=36), nullable=False),
        Column('name', String(length=255)),
        UniqueConstraint(
            'uuid', name='uniq_instance_groups0uuid'),
        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )

    group_policy = Table('instance_group_policy', meta,
        Column('created_at', DateTime),
        Column('updated_at', DateTime),
        Column('id', Integer, primary_key=True, nullable=False),
        Column('policy', String(length=255)),
        Column(
            'group_id', Integer, ForeignKey('instance_groups.id'),
            nullable=False),
        Index('instance_group_policy_policy_idx', 'policy'),
        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )

    group_member = Table('instance_group_member', meta,
        Column('created_at', DateTime),
        Column('updated_at', DateTime),
        Column('id', Integer, primary_key=True, nullable=False),
        Column('instance_uuid', String(length=255)),
        Column(
            'group_id', Integer, ForeignKey('instance_groups.id'),
            nullable=False),
        Index('instance_group_member_instance_idx', 'instance_uuid'),
        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )

    tables = [
        cell_mappings,
        host_mappings,
        instance_mappings,
        flavors,
        flavor_extra_specs,
        flavor_projects,
        request_specs,
        build_requests,
        keypairs,
        resource_providers,
        inventories,
        allocations,
        resource_provider_aggregates,
        aggregates,
        aggregate_hosts,
        aggregate_metadata,
        groups,
        group_policy,
        group_member,
    ]
    for table in tables:
        table.create(checkfirst=True)
