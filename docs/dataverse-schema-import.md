# Dataverse Schema Import

`app.models.dataverse` reads an unpacked `customizations.xml` file and creates a SQLite table for each exported Dataverse entity. It removes the `cr882_` publisher prefix from every imported table and column name.

The current solution imports these tables with the `cr882_` publisher prefix removed.

- `actions_list`
- `meeting`
- `meeting_agendas`
- `meeting_minutes`
- `meetingagenda`
- `topic_intake`
- `topics_list`
- `new_topic_folder_registry`

SQLite does not implement Dataverse-specific GUID, lookup, owner, option set, state, and status column types. The importer uses compatible storage: GUID and reference values are strings, choices and status values are integers, dates use datetime storage, and text preserves its configured maximum length where one exists.

Set `PPM_SOLUTION_EXPORT_DIRECTORY` when more than one unpacked solution is present. The directory must contain exactly one direct child with `customizations.xml`; this prevents accidentally importing an unintended solution.