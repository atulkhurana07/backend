"""public platform models

Revision ID: 001
Revises: 
Create Date: 2026-08-31 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Add charging_center_status enum type
    charging_center_status_enum = postgresql.ENUM('OPERATIONAL', 'LIMITED', 'OFFLINE', 'UNDER_MAINTENANCE', name='charging_center_status_enum')
    charging_center_status_enum.create(op.get_bind(), checkfirst=True)
    
    # 2. Add charging_center_operator to user_role enum
    # In PostgreSQL, altering ENUMs can be tricky. We assume user_role enum exists.
    # Note: Adding value to enum in a simple way for postgres
    try:
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE user_role ADD VALUE 'charging_center_operator'")
    except Exception:
        pass
    
    # 3. Add new columns to charging_centers table
    op.add_column('charging_centers', sa.Column('address', sa.String(length=500), nullable=True))
    op.add_column('charging_centers', sa.Column('city', sa.String(length=100), nullable=True))
    op.add_column('charging_centers', sa.Column('state', sa.String(length=100), nullable=True))
    op.add_column('charging_centers', sa.Column('pincode', sa.String(length=10), nullable=True))
    op.add_column('charging_centers', sa.Column('status', sa.Enum('OPERATIONAL', 'LIMITED', 'OFFLINE', 'UNDER_MAINTENANCE', name='charging_center_status_enum'), server_default='OPERATIONAL', nullable=False))
    op.add_column('charging_centers', sa.Column('description', sa.String(length=1000), nullable=True))
    op.add_column('charging_centers', sa.Column('amenities', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('charging_centers', sa.Column('contact_phone', sa.String(length=20), nullable=True))
    op.add_column('charging_centers', sa.Column('operating_hours', sa.String(length=100), nullable=True))
    
    op.create_index(op.f('ix_charging_centers_city'), 'charging_centers', ['city'], unique=False)
    op.create_index(op.f('ix_charging_centers_state'), 'charging_centers', ['state'], unique=False)

    # 4. Create charging_center_operators table
    op.create_table('charging_center_operators',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('charging_center_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['charging_center_id'], ['charging_centers.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'charging_center_id', name='uq_user_charging_center')
    )
    op.create_index(op.f('ix_charging_center_operators_charging_center_id'), 'charging_center_operators', ['charging_center_id'], unique=False)
    op.create_index(op.f('ix_charging_center_operators_user_id'), 'charging_center_operators', ['user_id'], unique=False)

    # 5. Create cities table
    op.create_table('cities',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('state', sa.String(length=100), nullable=False),
    sa.Column('latitude', sa.Float(), nullable=True),
    sa.Column('longitude', sa.Float(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name', 'state', name='uq_city_state')
    )
    op.create_index(op.f('ix_cities_name'), 'cities', ['name'], unique=False)
    op.create_index(op.f('ix_cities_state'), 'cities', ['state'], unique=False)

    # 6. Create routes table
    op.create_table('routes',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('code', sa.String(length=50), nullable=True),
    sa.Column('city', sa.String(length=100), nullable=False),
    sa.Column('state', sa.String(length=100), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=True),
    sa.Column('geometry', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('color', sa.String(length=7), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_routes_city'), 'routes', ['city'], unique=False)
    op.create_index(op.f('ix_routes_code'), 'routes', ['code'], unique=False)
    op.create_index(op.f('ix_routes_state'), 'routes', ['state'], unique=False)

    # 7. Create stops table
    op.create_table('stops',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('code', sa.String(length=50), nullable=True),
    sa.Column('latitude', sa.Float(), nullable=False),
    sa.Column('longitude', sa.Float(), nullable=False),
    sa.Column('city', sa.String(length=100), nullable=False),
    sa.Column('state', sa.String(length=100), nullable=False),
    sa.Column('address', sa.String(length=500), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_stops_city'), 'stops', ['city'], unique=False)
    op.create_index(op.f('ix_stops_state'), 'stops', ['state'], unique=False)

    # 8. Create route_stops table
    op.create_table('route_stops',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('route_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('stop_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('distance_from_start_km', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['route_id'], ['routes.id'], ),
    sa.ForeignKeyConstraint(['stop_id'], ['stops.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('route_id', 'sequence', name='uq_route_sequence'),
    sa.UniqueConstraint('route_id', 'stop_id', name='uq_route_stop')
    )
    op.create_index(op.f('ix_route_stops_route_id'), 'route_stops', ['route_id'], unique=False)
    op.create_index(op.f('ix_route_stops_stop_id'), 'route_stops', ['stop_id'], unique=False)

    # 9. Create vehicle_routes table
    op.create_table('vehicle_routes',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('vehicle_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('route_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('direction', sa.String(length=20), nullable=True),
    sa.ForeignKeyConstraint(['route_id'], ['routes.id'], ),
    sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_vehicle_routes_route_id'), 'vehicle_routes', ['route_id'], unique=False)
    op.create_index(op.f('ix_vehicle_routes_vehicle_id'), 'vehicle_routes', ['vehicle_id'], unique=False)

    # 10. Create help_contacts table
    op.create_table('help_contacts',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('city', sa.String(length=100), nullable=True),
    sa.Column('state', sa.String(length=100), nullable=True),
    sa.Column('department', sa.String(length=200), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=True),
    sa.Column('phone', sa.String(length=20), nullable=True),
    sa.Column('email', sa.String(length=200), nullable=True),
    sa.Column('description', sa.String(length=500), nullable=True),
    sa.Column('category', sa.String(length=100), nullable=False),
    sa.Column('availability', sa.String(length=100), nullable=True),
    sa.Column('public_visible', sa.Boolean(), nullable=False),
    sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_help_contacts_city'), 'help_contacts', ['city'], unique=False)
    op.create_index(op.f('ix_help_contacts_state'), 'help_contacts', ['state'], unique=False)


def downgrade() -> None:
    op.drop_table('help_contacts')
    op.drop_table('vehicle_routes')
    op.drop_table('route_stops')
    op.drop_table('stops')
    op.drop_table('routes')
    op.drop_table('cities')
    op.drop_table('charging_center_operators')
    
    op.drop_column('charging_centers', 'operating_hours')
    op.drop_column('charging_centers', 'contact_phone')
    op.drop_column('charging_centers', 'amenities')
    op.drop_column('charging_centers', 'description')
    op.drop_column('charging_centers', 'status')
    op.drop_column('charging_centers', 'pincode')
    op.drop_column('charging_centers', 'state')
    op.drop_column('charging_centers', 'city')
    op.drop_column('charging_centers', 'address')
    
    op.execute("DROP TYPE charging_center_status_enum")
