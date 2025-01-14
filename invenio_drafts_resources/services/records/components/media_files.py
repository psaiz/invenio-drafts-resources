# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2021 CERN.
# Copyright (C) 2021 Northwestern University.
# Copyright (C) 2023 Graz University of Technology.
#
# Invenio-Drafts-Resources is free software; you can redistribute it and/or
# modify it under the terms of the MIT License; see LICENSE file for more
# details.

"""Records service component base classes."""
from invenio_i18n import gettext as _
from invenio_records_resources.services.base.config import _make_cls
from marshmallow import ValidationError

from .base import BaseRecordFilesComponent


class _DraftMediaFilesComponent(BaseRecordFilesComponent):
    """Draft media files component."""

    def create(self, identity, data=None, record=None, errors=None):
        """Assigns files.enabled.

        NOTE: `record` actually refers to the draft
              (this interface is used in records-resources and rdm-records)
        """
        draft = record
        files = self.get_record_files(draft)

        # disable the media files by default
        enabled = data.get(self.files_data_key, {}).get("enabled", False)

        files.enabled = enabled

    def update_draft(self, identity, data=None, record=None, errors=None):
        """Assigns files.enabled and warns if files are missing.

        NOTE: `record` actually refers to the draft
              (this interface is used in records-resources and rdm-records)
        """
        draft = record
        draft_files = self.get_record_files(draft)
        record_files = self.get_record_files(record)
        enabled = data.get(self.files_data_key, {}).get("enabled", record_files.enabled)
        default_preview = data.get(self.files_data_key, {}).get("default_preview")

        try:
            self.assign_files_enabled(draft, enabled)
        except ValidationError as e:
            errors.append(
                {"field": f"{self.files_data_key}.enabled", "messages": e.messages}
            )
            return  # exit early

        if draft_files.enabled and not draft_files.items():
            errors.append(
                {
                    "field": f"{self.files_data_key}.enabled",
                    "messages": [
                        _(
                            "Missing uploaded files. To disable files for "
                            "this record please mark it as metadata-only."
                        )
                    ],
                }
            )

        try:
            self.assign_files_default_preview(
                draft,
                default_preview,
            )
        except ValidationError as e:
            errors.append(
                {
                    "field": f"{self.files_data_key}.default_preview",
                    "messages": e.messages,
                }
            )

    def edit(self, identity, draft=None, record=None):
        """Edit callback."""
        draft_files = self.get_record_files(draft)
        record_files = self.get_record_files(record)
        draft_bucket = self.get_record_bucket(draft)
        if draft_bucket is None:
            # Happens, when a soft-deleted draft is un-deleted.
            draft[self.files_data_key] = {"enabled": record_files.enabled}
            # re-fetch the files attribute - above data getter sets the attribute
            draft_files = self.get_record_files(draft)
            draft_files.create_bucket()
        draft_files.copy(record_files)
        # in the media files we don't lock the bucket
        # - they can be simply edited from draft

    def _publish_edit(self, identity, draft, record):
        """Action when publishing an edit to an existing record."""
        # TODO: For published records, we should sync changes from the
        # draft bucket to the record bucket, so that an instance could
        # potentially allow a user to update files. For now, sync() only
        # changes the default_preview and order
        record_files = self.get_record_files(record)
        draft_files = self.get_record_files(draft)
        record_files.sync(draft_files)
        record_files.unlock()
        record_files.copy(draft_files)
        record_files.lock()
        # Teardown the bucket and files created in edit().
        if draft_files.enabled:
            draft_files.delete_all()
        draft_files.remove_bucket(force=True)

    def new_version(self, identity, draft=None, record=None):
        """New version callback."""
        # We don't copy files from the previous version, but instead allow
        # users to import the files.
        draft_files = self.get_record_files(draft)
        record_files = self.get_record_files(record)
        draft_files.enabled = record_files.enabled
        draft_files.copy(record_files)

    def import_files(self, identity, draft=None, record=None):
        """Import files callback."""
        # We don't need the import for media files
        return


MediaFilesAttrConfig = {
    "_files_attr_key": "media_files",
    "_files_data_key": "media_files",
    "_files_bucket_attr_key": "media_bucket",
    "_files_bucket_id_attr_key": "media_bucket_id",
}

### Configure file attributes for media files component
DraftMediaFilesComponent = _make_cls(
    _DraftMediaFilesComponent, {**MediaFilesAttrConfig}
)
