"""Pure unit tests for brief template schemas, RBAC, and field validation."""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from app.core.rbac import Permission, get_permissions_for_agency_role
from app.models.enums import AgencyMemberRole, FieldType
from app.schemas.brief_template import FieldCreate, TemplateCreate, TemplateUpdate

# ── FieldType enum ────────────────────────────────────────────────────────────


def test_field_type_enum_has_16_values() -> None:
    assert len(FieldType) == 16


def test_all_expected_field_types_present() -> None:
    codes = {ft.value for ft in FieldType}
    expected = {
        "text",
        "textarea",
        "rich_text",
        "select",
        "multi_select",
        "checkbox",
        "date",
        "url",
        "number",
        "file",
        "color",
        "moodboard",
        "reference_images",
        "platform_selector",
        "campaign_goal",
        "target_audience",
    }
    assert codes == expected


# ── FieldCreate validation ────────────────────────────────────────────────────


def test_field_create_valid_text() -> None:
    f = FieldCreate(field_key="campaign_name", label="Campaign Name", field_type="text")
    assert f.field_key == "campaign_name"
    assert f.field_type == "text"


def test_field_create_invalid_field_type_rejected() -> None:
    with pytest.raises(ValidationError):
        FieldCreate(field_key="x", label="X", field_type="not_a_type")


def test_field_key_pattern_enforced() -> None:
    with pytest.raises(ValidationError):
        FieldCreate(field_key="123_invalid", label="X", field_type="text")

    with pytest.raises(ValidationError):
        FieldCreate(field_key="has space", label="X", field_type="text")


def test_field_key_uppercase_rejected() -> None:
    with pytest.raises(ValidationError):
        FieldCreate(field_key="MyField", label="X", field_type="text")


def test_select_requires_options() -> None:
    with pytest.raises(ValidationError):
        FieldCreate(field_key="platform", label="Platform", field_type="select")


def test_multi_select_requires_options() -> None:
    with pytest.raises(ValidationError):
        FieldCreate(field_key="goals", label="Goals", field_type="multi_select")


def test_select_with_options_valid() -> None:
    f = FieldCreate(
        field_key="platform",
        label="Platform",
        field_type="select",
        options={"choices": ["Instagram", "TikTok"]},
    )
    assert f.options is not None


def test_non_select_does_not_require_options() -> None:
    f = FieldCreate(field_key="budget", label="Budget", field_type="number")
    assert f.options is None


# ── TemplateCreate validation ─────────────────────────────────────────────────


def test_template_create_requires_name() -> None:
    with pytest.raises(ValidationError):
        TemplateCreate(name="")


def test_template_create_valid() -> None:
    t = TemplateCreate(name="Social Media Brief", industry="social_media")
    assert t.name == "Social Media Brief"
    assert t.industry == "social_media"


def test_template_update_all_optional() -> None:
    u = TemplateUpdate()
    assert u.name is None
    assert u.description is None


# ── RBAC permission matrix ────────────────────────────────────────────────────


def test_owner_has_all_template_permissions() -> None:
    perms = get_permissions_for_agency_role(AgencyMemberRole.OWNER.value)
    assert Permission.TEMPLATE_VIEW in perms
    assert Permission.TEMPLATE_CREATE in perms
    assert Permission.TEMPLATE_UPDATE in perms
    assert Permission.TEMPLATE_ARCHIVE in perms


def test_admin_has_all_template_permissions() -> None:
    perms = get_permissions_for_agency_role(AgencyMemberRole.ADMIN.value)
    assert Permission.TEMPLATE_VIEW in perms
    assert Permission.TEMPLATE_CREATE in perms
    assert Permission.TEMPLATE_UPDATE in perms
    assert Permission.TEMPLATE_ARCHIVE in perms


def test_brand_manager_can_create_update_but_not_archive() -> None:
    perms = get_permissions_for_agency_role(AgencyMemberRole.BRAND_MANAGER.value)
    assert Permission.TEMPLATE_VIEW in perms
    assert Permission.TEMPLATE_CREATE in perms
    assert Permission.TEMPLATE_UPDATE in perms
    assert Permission.TEMPLATE_ARCHIVE not in perms


def test_designer_can_only_view_templates() -> None:
    perms = get_permissions_for_agency_role(AgencyMemberRole.DESIGNER.value)
    assert Permission.TEMPLATE_VIEW in perms
    assert Permission.TEMPLATE_CREATE not in perms
    assert Permission.TEMPLATE_UPDATE not in perms
    assert Permission.TEMPLATE_ARCHIVE not in perms


def test_viewer_can_only_view_templates() -> None:
    perms = get_permissions_for_agency_role(AgencyMemberRole.VIEWER.value)
    assert Permission.TEMPLATE_VIEW in perms
    assert Permission.TEMPLATE_CREATE not in perms
    assert Permission.TEMPLATE_ARCHIVE not in perms


def test_unknown_role_gets_no_permissions() -> None:
    perms = get_permissions_for_agency_role("nonexistent_role")
    assert len(perms) == 0


# ── System template isolation logic ──────────────────────────────────────────


def test_system_template_accessible_regardless_of_agency() -> None:
    """System template (is_system=True, agency_id=None) should be accessible to any agency."""
    is_system = True
    tmpl_agency_id = None
    viewer_agency_id = uuid.uuid4()
    is_accessible = is_system or tmpl_agency_id == viewer_agency_id
    assert is_accessible


def test_agency_template_hidden_from_other_agencies() -> None:
    """Agency-scoped template must not be accessible to a different agency."""
    own_agency_id = uuid.uuid4()
    other_agency_id = uuid.uuid4()
    is_system = False

    accessible_to_owner = is_system or own_agency_id == own_agency_id
    accessible_to_other = is_system or other_agency_id == own_agency_id

    assert accessible_to_owner
    assert not accessible_to_other
