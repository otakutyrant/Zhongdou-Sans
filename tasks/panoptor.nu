# nu-lint-ignore-file: unhandled_external_error
# Per-worktree Process Compose discovery and lifecycle control.

const PROJECT_ROOT = path self | path dirname | path dirname
const CONFIG_FILE = $PROJECT_ROOT | path join process-compose.yaml
const PROJECT_NAME = "zhongdou-sans"
const MAIN_PORT = 8000
const SECONDARY_PORT_BASE = 10000
const SECONDARY_PORT_SPAN = 20000

def now []: nothing -> string {
    date now | into string
}

def repository-root []: nothing -> string {
    let result = (^git -C $PROJECT_ROOT rev-parse --show-toplevel | complete)
    if $result.exit_code != 0 {
        error make { msg: ($result.stderr | str trim) }
    }
    $result.stdout | str trim | path expand
}

def main-worktree-root []: nothing -> string {
    let result = (
        ^git -C $PROJECT_ROOT rev-parse --path-format=absolute --git-common-dir
        | complete
    )
    if $result.exit_code != 0 {
        error make { msg: ($result.stderr | str trim) }
    }
    $result.stdout | str trim | path dirname | path expand
}

def worktree-id []: nothing -> string {
    repository-root | hash sha256 | str substring 0..11
}

def runtime-directory []: nothing -> string {
    let runtime_root = $env.XDG_RUNTIME_DIR? | default ($env.TMPDIR? | default "/tmp")
    $runtime_root | path join $PROJECT_NAME $"panoptor-(worktree-id)"
}

def socket-path []: nothing -> string {
    runtime-directory | path join process-compose.sock
}

def session-state-path []: nothing -> string {
    runtime-directory | path join session.json
}

def server-log-path []: nothing -> string {
    runtime-directory | path join process-compose.log
}

def task-state-path [role: string]: nothing -> string {
    runtime-directory | path join $"($role)-task.json"
}

def atomic-save [path: string value: any] {
    mkdir ($path | path dirname)
    let temporary = $"($path).($nu.pid).tmp"
    $value | to json | save --force $temporary
    mv --force $temporary $path
}

def read-record [path: string]: nothing -> any {
    if not ($path | path exists) {
        return null
    }
    try { open $path } catch { null }
}

def default-port []: nothing -> int {
    if (repository-root) == (main-worktree-root) {
        $MAIN_PORT
    } else {
        let prefix = worktree-id | str substring 0..3 | into int --radix 16
        $SECONDARY_PORT_BASE + ($prefix mod $SECONDARY_PORT_SPAN)
    }
}

def configured-port []: nothing -> int {
    let state_path = session-state-path
    if ($state_path | path exists) {
        try { open $state_path | get port | into int } catch { default-port }
    } else {
        default-port
    }
}

def client [arguments: list<string>]: nothing -> record {
    ^process-compose --use-uds --unix-socket (socket-path) ...$arguments | complete
}

def require-session [] {
    if (client [list --output json]).exit_code != 0 {
        error make {
            msg: "Panoptor is stopped."
            help: "Run `nur panoptor start`."
        }
    }
}

def require-role [role: string] {
    if $role not-in [site checks] {
        error make { msg: "Role must be `site` or `checks`." }
    }
}

def port-available [port: int]: nothing -> bool {
    let script = "import socket, sys; s = socket.socket(); s.bind(('127.0.0.1', int(sys.argv[1]))); s.close()"
    (^python -c $script ($port | into string) | complete).exit_code == 0
}

def wait-for-session [] {
    for _ in 1..100 {
        if (client [list --output json]).exit_code == 0 {
            return
        }
        sleep 50ms
    }
    error make {
        msg: "Panoptor did not expose its Process Compose socket."
        help: $"Inspect (server-log-path)."
    }
}

def wait-for-shutdown [] {
    for _ in 1..100 {
        if (client [list --output json]).exit_code != 0 {
            return
        }
        sleep 50ms
    }
    error make { msg: "Panoptor did not stop in time." }
}

def print-client-error [result: record] {
    let message = $result.stderr | str trim
    error make { msg: (if ($message | is-empty) { "Process Compose command failed." } else { $message }) }
}

def owns-snapshot []: nothing -> bool {
    let owner = $env.PANOPTOR_WORKTREE_ID? | default ""
    $owner == (worktree-id)
}

def run-streaming [command: list<string>]: nothing -> int {
    let executable = $command | first
    let arguments = $command | skip 1
    let result = try {
        ^$executable ...$arguments
        { exit_code: $env.LAST_EXIT_CODE error: null }
    } catch {|error|
        let observed = $env.LAST_EXIT_CODE? | default 1
        {
            exit_code: (if $observed == 0 { 1 } else { $observed })
            error: ($error.msg? | default "External command failed.")
        }
    }
    if $result.error != null {
        print --stderr $result.error
    }
    $result.exit_code
}

# Run one command while atomically publishing its latest Panoptor result.
export def run-with-panoptor-snapshot [role: string command: list<string>] {
    require-role $role
    if not (owns-snapshot) {
        let exit_code = run-streaming $command
        if $exit_code != 0 {
            exit $exit_code
        }
        return
    }

    let started_at = now
    atomic-save (task-state-path $role) {
        role: $role
        state: "running"
        command: $command
        started_at: $started_at
        finished_at: null
        exit_code: null
    }
    let exit_code = run-streaming $command
    atomic-save (task-state-path $role) {
        role: $role
        state: (if $exit_code == 0 { "passed" } else { "failed" })
        command: $command
        started_at: $started_at
        finished_at: (now)
        exit_code: $exit_code
    }
    if $exit_code != 0 {
        exit $exit_code
    }
}

# Start this worktree's isolated Panoptor server without opening a TUI.
export def "nur panoptor start" [--port: int] {
    if (client [list --output json]).exit_code == 0 {
        error make { msg: "Panoptor is already running. Use `nur panoptor status`." }
    }
    let selected_port = $port | default (default-port)
    if not (port-available $selected_port) {
        error make {
            msg: $"Port ($selected_port) is unavailable."
            help: "Choose another port with `nur panoptor start --port <port>`."
        }
    }
    mkdir (runtime-directory)
    {
        project: $PROJECT_NAME
        worktree: (repository-root)
        worktree_id: (worktree-id)
        port: $selected_port
        socket: (socket-path)
    } | save --force (session-state-path)
    for role in [site checks] {
        let stale_state = task-state-path $role
        if ($stale_state | path exists) {
            rm $stale_state
        }
    }

    with-env {
        PANOPTOR_PROJECT_ROOT: (repository-root)
        PANOPTOR_SITE_PORT: ($selected_port | into string)
        PANOPTOR_WORKTREE_ID: (worktree-id)
    } {
        let arguments = [
            --config
            $CONFIG_FILE
            --use-uds
            --unix-socket
            (socket-path)
            --log-file
            (server-log-path)
            --detached
            --keep-project
            up
        ]
        ^process-compose ...$arguments
    }
    wait-for-session
    print $"Started headless Panoptor session `(worktree-id)` on port ($selected_port)."
}

# Report Process Compose's session and per-role state.
export def "nur panoptor status" [--json] {
    let result = client [list --output json]
    let running = $result.exit_code == 0
    let processes = if $running {
        try { $result.stdout | from json } catch { [] }
    } else {
        []
    }
    let latest_checks = if $running {
        read-record (task-state-path checks)
    } else {
        null
    }
    let status = {
        project: $PROJECT_NAME
        worktree: (repository-root)
        worktree_id: (worktree-id)
        session: (if $running { "running" } else { "stopped" })
        socket: (socket-path)
        port: (configured-port)
        processes: $processes
        latest_tasks: {
            checks: $latest_checks
        }
    }
    if $json {
        $status | to json | print
    } else {
        print $"Panoptor session: ($status.session)"
        print $"Worktree: ($status.worktree_id)  Site port: ($status.port)"
        if $running {
            $processes | print
            if $latest_checks != null {
                print $"Latest checks: ($latest_checks.state)"
            }
        }
    }
}

# Check declared readiness probes, optionally waiting for them to succeed.
export def "nur panoptor ready" [--wait] {
    require-session
    let arguments = if $wait {
        [project is-ready --wait]
    } else {
        [project is-ready]
    }
    let result = client $arguments
    if $result.exit_code != 0 {
        print-client-error $result
    }
    print --no-newline $result.stdout
}

# Attach an interactive TUI; quitting the TUI leaves the session running.
export def "nur panoptor attach" [] {
    require-session
    ^process-compose --use-uds --unix-socket (socket-path) attach
}

# Read bounded recent output from one role without entering the TUI.
export def "nur panoptor inspect" [role: string --lines: int = 80] {
    require-role $role
    require-session
    let result = client [process logs $role --tail ($lines | into string)]
    if $result.exit_code != 0 {
        print-client-error $result
    }
    print --no-newline $result.stdout
}

# Stop one role. The declared roles stay non-interactive so Process Compose can
# retain their line logs for both agents and the TUI.
export def "nur panoptor interrupt" [role: string] {
    require-role $role
    require-session
    let result = client [process stop $role]
    if $result.exit_code != 0 {
        print-client-error $result
    }
}

# Start a stopped role with its declared Process Compose command.
export def "nur panoptor start-role" [role: string] {
    require-role $role
    require-session
    let result = client [process start $role]
    if $result.exit_code != 0 {
        print-client-error $result
    }
}

# Stop a role without terminating the rest of the Panoptor session.
export def "nur panoptor stop-role" [role: string] {
    nur panoptor interrupt $role
}

# Restart a role with its currently declared Process Compose command.
export def "nur panoptor restart" [role: string] {
    require-role $role
    require-session
    let result = client [process restart $role]
    if $result.exit_code != 0 {
        print-client-error $result
    }
}

# Stop only this worktree's Process Compose server and all of its roles.
export def "nur panoptor stop" [] {
    require-session
    let result = client [down]
    if $result.exit_code != 0 {
        print-client-error $result
    }
    wait-for-shutdown
}
