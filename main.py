import os
import uuid
import json

from flask import Flask, request, jsonify
from werkzeug.serving import WSGIRequestHandler

from openrelik_api_client.api_client import APIClient
from openrelik_api_client.folders import FoldersAPI
from openrelik_api_client.workflows import WorkflowsAPI

# --------------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------------
API_SERVER_URL = "http://localhost:8710"
API_KEY = os.getenv("OPENRELIK_API_KEY", "your_api_key")

# Initialize API clients
api_client = APIClient(API_SERVER_URL, API_KEY)
folders_api = FoldersAPI(api_client)
workflows_api = WorkflowsAPI(api_client)

# --------------------------------------------------------------------------------
# Initialize Flask app
# --------------------------------------------------------------------------------
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB limit


# --------------------------------------------------------------------------------
# Helper functions
# --------------------------------------------------------------------------------
def create_folder(folder_name):
    """
    Create a new root folder with the given folder name.
    """
    response = folders_api.create_root_folder(folder_name)
    return response


def upload_file(file_path, folder_id):
    """
    Upload a file to the specified folder.
    """
    response = api_client.upload_file(file_path, folder_id)
    return response


def create_workflow(folder_id, file_ids):
    """
    Create a new workflow in the specified folder with the given file IDs.
    Returns the workflow ID and the workflow's folder ID.
    """
    response = workflows_api.create_workflow(folder_id, file_ids)
    workflow_id = response
    workflow = workflows_api.get_workflow(folder_id, workflow_id)
    return workflow_id, workflow["folder"]["id"]


def rename_folder(folder_id, new_name):
    """
    Rename an existing folder.
    """
    return folders_api.update_folder(folder_id, {"display_name": new_name})


def rename_workflow(folder_id, workflow_id, new_name):
    """
    Rename an existing workflow.
    """
    return workflows_api.update_workflow(folder_id, workflow_id, {"display_name": new_name})


def add_tasks_to_workflow(folder_id, workflow_id, sketch_name):
    """
    Add tasks to an existing workflow, including a Plaso task and a Timesketch task.
    """
    plaso_task_uuid = str(uuid.uuid4()).replace("-", "")
    timesketch_task_uuid = str(uuid.uuid4()).replace("-", "")

    workflow_spec = {
        "spec_json": json.dumps({
            "workflow": {
                "type": "chain",
                "isRoot": True,
                "tasks": [
                    {
                        "task_name": "openrelik-worker-plaso.tasks.log2timeline",
                        "queue_name": "openrelik-worker-plaso",
                        "display_name": "Plaso: Log2Timeline",
                        "description": "Super timelining",
                        "task_config": [
                            {
                                "name": "artifacts",
                                "label": "Select artifacts to parse",
                                "description": (
                                    "Select one or more forensic artifact definitions "
                                    "from the ForensicArtifacts project. These definitions "
                                    "specify files and data relevant to digital forensic "
                                    "investigations. Only the selected artifacts will be "
                                    "parsed."
                                ),
                                "type": "artifacts",
                                "required": False
                            },
                            {
                                "name": "parsers",
                                "label": "Select parsers to use",
                                "description": (
                                    "Select one or more Plaso parsers. These parsers specify "
                                    "how to interpret files and data. Only data identified by "
                                    "the selected parsers will be processed."
                                ),
                                "type": "autocomplete",
                                "items": [
                                    "winreg/amcache", "sqlite/dropbox", "text/skydrive_log_v2",
                                    "winreg/ccleaner", "sqlite/twitter_android",
                                    "plist/macos_login_window_plist", "text/cri_log",
                                    "text/powershell_transcript", "winevt", "olecf/olecf_automatic_destinations",
                                    "text/viminfo", "plist/ipod_device", "czip/oxml",
                                    "plist/airport", "plist/time_machine", "wincc_sys",
                                    "text", "text/xchatscrollback", "utmpx", "jsonl/aws_cloudtrail_log",
                                    "plist/macos_install_history", "pls_recall", "plist/macos_bluetooth",
                                    "sqlite/chrome_8_history", "sqlite/hangouts_messages", "winreg/bam",
                                    "text/android_logcat", "text/setupapi",
                                    "winreg/mrulist_shell_item_list", "winreg/windows_task_cache",
                                    "winpca_dic", "winreg/mrulistex_shell_item_list", "winreg/mstsc_rdp",
                                    "winreg/microsoft_outlook_mru", "sqlite/android_calls",
                                    "sqlite/windows_push_notification", "winreg/windows_run",
                                    "text/winfirewall", "spotlight_storedb", "sqlite/safari_historydb",
                                    "text/gdrive_synclog", "esedb", "text/teamviewer_connections_incoming",
                                    "text/mac_appfirewall_log", "sqlite/ios_screentime", "winevtx",
                                    "sqlite/appusage", "text/confluence_access", "mft", "winreg/windows_version",
                                    "onedrive_log", "text/popularity_contest", "winreg/windows_services",
                                    "windefender_history", "winreg/windows_usbstor_devices",
                                    "plist/ios_identityservices", "usnjrnl", "trendmicro_vd", "prefetch",
                                    "text/aws_elb_access", "mac_keychain", "sqlite/edge_load_statistics",
                                    "filestat", "jsonl/azure_activity_log", "sqlite/android_webviewcache",
                                    "sqlite/imessage", "sqlite/chrome_17_cookies", "plist/safari_history",
                                    "msiecf", "sqlite/ios_powerlog", "sqlite/firefox_history", "locate_database",
                                    "text/snort_fastlog", "esedb/msie_webcache", "jsonl/docker_container_log",
                                    "trendmicro_url", "sqlite/mac_document_versions", "text/ios_lockdownd",
                                    "winreg/bagmru", "chrome_preferences", "sqlite/ls_quarantine",
                                    "sqlite/ios_datausage", "sqlite", "simatic_s7", "czip",
                                    "plist/macos_login_items_plist", "plist/plist_default",
                                    "winreg/mrulist_string", "sqlite/firefox_118_downloads",
                                    "text/teamviewer_application_log", "firefox_cache",
                                    "sqlite/android_webview", "winreg", "winpca_db0",
                                    "text/teamviewer_connections_outgoing", "sqlite/twitter_ios", "olecf",
                                    "bsm_log", "opera_global", "text/googlelog", "android_app_usage",
                                    "mcafee_protection", "winreg/microsoft_office_mru",
                                    "sqlite/windows_eventtranscript", "asl_log", "fish_history",
                                    "winreg/explorer_mountpoints2", "sqlite/kodi", "winreg/mrulistex_string",
                                    "winreg/networks", "text/winiis", "sqlite/android_sms", "cups_ipp",
                                    "winreg/winrar_mru", "lnk", "bencode/bencode_utorrent", "jsonl",
                                    "plist/launchd_plist", "winreg/windows_sam_users", "plist/macuser",
                                    "text/skydrive_log_v1", "text/mac_wifi", "plist/spotlight",
                                    "symantec_scanlog", "text/ios_sysdiag_log", "winreg/msie_zone",
                                    "winreg/userassist", "jsonl/ios_application_privacy", "sqlite/chrome_27_history",
                                    "text/vsftpd", "bencode/bencode_transmission", "fseventsd", "olecf/olecf_default",
                                    "jsonl/microsoft_audit_log", "unified_logging", "java_idx",
                                    "sqlite/chrome_extension_activity", "sqlite/kik_ios", "opera_typed_history",
                                    "sqlite/windows_timeline", "text/sccm", "sqlite/tango_android_profile",
                                    "sqlite/firefox_10_cookies", "sqlite/macostcc", "text/macos_launchd_log",
                                    "chrome_cache", "custom_destinations", "winreg/network_drives",
                                    "plist/ios_carplay", "olecf/olecf_summary", "sqlite/tango_android_tc",
                                    "utmp", "sqlite/chrome_autofill", "sqlite/firefox_downloads", "bodyfile",
                                    "sqlite/android_app_usage", "text/selinux", "plist/macos_software_update",
                                    "pe", "plist/apple_id", "text/syslog_traditional", "winreg/windows_boot_execute",
                                    "systemd_journal", "firefox_cache2", "text/apache_access",
                                    "plist/macos_background_items_plist", "jsonl/docker_layer_config",
                                    "winreg/windows_boot_verify", "text/ios_logd", "networkminer_fileinfo",
                                    "winreg/mrulistex_string_and_shell_item", "esedb/file_history",
                                    "sqlite/mac_notes", "sqlite/chrome_66_cookies", "text/sophos_av",
                                    "esedb/srum", "bencode", "winreg/winreg_default", "text/xchatlog",
                                    "sqlite/zeitgeist", "text/postgresql", "sqlite/firefox_2_cookies",
                                    "winreg/windows_usb_devices", "winreg/windows_timezone", "binary_cookies",
                                    "winjob", "recycle_bin_info2", "plist/safari_downloads",
                                    "sqlite/ios_netusage", "text/apt_history", "plist/spotlight_volume",
                                    "sqlite/skype", "sqlite/google_drive", "winreg/windows_typed_urls",
                                    "jsonl/docker_container_config", "text/dpkg", "text/zsh_extended_history",
                                    "text/syslog", "sqlite/mackeeper_cache", "winreg/mstsc_rdp_mru",
                                    "winreg/windows_shutdown", "olecf/olecf_document_summary",
                                    "winreg/appcompatcache", "winreg/mrulistex_string_and_shell_item_list",
                                    "text/santa", "winreg/winlogon", "text/bash_history",
                                    "text/mac_securityd", "recycle_bin", "sqlite/android_turbo",
                                    "jsonl/azure_application_gateway_access_log", "rplog",
                                    "winreg/explorer_programscache", "esedb/user_access_logging",
                                    "jsonl/gcp_log", "sqlite/mac_knowledgec", "plist/macos_startup_item_plist",
                                    "plist"
                                ],
                                "required": False
                            },
                            {
                                "name": "archives",
                                "label": "Archives",
                                "description": (
                                    "Select one or more Plaso archive types. "
                                    "Files inside these archive types will be processed."
                                ),
                                "type": "autocomplete",
                                "items": ["iso9660", "modi", "tar", "vhdi", "zip"],
                                "required": False
                            }
                        ],
                        "type": "task",
                        "uuid": f"{plaso_task_uuid}",
                        "tasks": [
                            {
                                "task_name": "openrelik-worker-timesketch.tasks.upload",
                                "queue_name": "openrelik-worker-timesketch",
                                "display_name": "Upload to Timesketch",
                                "description": "Upload resulting file to Timesketch",
                                "task_config": [
                                    {
                                        "name": "sketch_name",
                                        "label": "Create a new sketch",
                                        "description": "Create a new sketch",
                                        "type": "text",
                                        "required": False,
                                        "value": f"{sketch_name}"
                                    }
                                ],
                                "type": "task",
                                "uuid": f"{timesketch_task_uuid}",
                                "tasks": []
                            }
                        ]
                    }
                ]
            }
        })
    }

    return workflows_api.update_workflow(folder_id, workflow_id, workflow_spec)


def run_workflow(folder_id, workflow_id):
    """
    Trigger the workflow execution.
    """
    return workflows_api.run_workflow(folder_id, workflow_id)


# --------------------------------------------------------------------------------
# Error handlers
# --------------------------------------------------------------------------------
@app.errorhandler(413)
def request_entity_too_large(error):
    """
    Return a 413 error if the file exceeds the maximum allowed size.
    """
    return "File is too large!", 413


# --------------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------------
@app.route("/api/upload", methods=["POST"])
def api_upload():
    """
    Endpoint to handle file uploads, create a workflow, and run it.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    filename = request.form.get("filename")

    if not filename:
        return jsonify({"error": "Filename and file are required"}), 400

    file_path = os.path.join("/tmp", filename)
    file.save(file_path)

    folder_id = create_folder(filename)
    file_id = upload_file(file_path, folder_id)
    workflow_id, workflow_folder_id = create_workflow(folder_id, [file_id])

    rename_folder(workflow_folder_id, f"{filename} Workflow Folder")
    rename_workflow(folder_id, workflow_id, f"{filename} Workflow")

    add_tasks_to_workflow(folder_id, workflow_id, filename)
    run = run_workflow(folder_id, workflow_id)

    return jsonify({
        "message": "Workflow started successfully",
        "workflow_id": workflow_id,
        "run_details": run
    })


# --------------------------------------------------------------------------------
# Main entry point
# --------------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="localhost", debug=True)
