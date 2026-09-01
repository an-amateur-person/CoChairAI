# Solution Migration Map

The exported `SAP_Meeting_Solution` is migrated as a meeting-governance application.

| Power Platform artifact | Python equivalent |
| --- | --- |
| `meeting` | Imported Dataverse table used by `/api/meetings` endpoints |
| `meetingagenda`, `meeting_agendas`, `topic_intake` | Imported tables used for agenda planning and topic intake |
| `actions_list` | Imported table used for topic action items |
| `meeting_minutes`, `topics_list` | Imported tables used for draft minutes and approvals |
| Meeting invitation flows | `invitation_requested` and `invitation_generated` state ready for a notification adapter |
| Reminder flow | APScheduler `meeting-reminder-scan` job with an environment-configured interval |
| SharePoint folders, Teams, Office 365, Copilot Studio | External adapters to add under `app/services`; connection details are intentionally not imported |

## Preserved design decisions

The solution export contains tenant-specific connection references and URLs. They are not copied into application code. Configure any future Microsoft Graph, SharePoint, or AI provider adapter through environment variables and a service implementation, keeping business values and credentials outside the source tree.