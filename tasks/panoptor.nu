# Per-worktree Process Compose discovery and lifecycle control.
# nu-lint-ignore-file: dont_mix_different_effects, missing_output_type
# nu-lint-ignore-file: print_and_return_data, unhandled_external_error

const PROJECT_ROOT = path self | path dirname | path dirname
const CONFIG_PATH = $PROJECT_ROOT | path join process-compose.yaml
const PROJECT_NAME = "zhongdou-sans"
const WORKTREE_PORT_BASE = 10000
const WORKTREE_PORT_SPAN = 20000

def repository-root []: nothing -> string {
    let result = ^git -C $PROJECT_ROOT rev-parse --show-toplevel | complete
    if $result.exit_code != 0 {
        error make {msg: ($result.stderr | str trim)}
    }
    $result.stdout | str trim | path expand
}

def worktree-id []: nothing -> string {
    repository-root | hash sha256 | str substring 0..11
}

def runtime-directory []: nothing -> string {
    let base = $env.XDG_RUNTIME_DIR? | default null
    if $base == null {
        error make {msg: "XDG_RUNTIME_DIR is required for Panoptor's private runtime state."}
    }
    $base | path join $PROJECT_NAME $"panoptor-(worktree-id)"
}

def socket-path []: nothing -> string {
    runtime-directory | path join process-compose.sock
}

def session-state-path []: nothing -> string {
    runtime-directory | path join session.json
}

def client-log-path []: nothing -> string {
    runtime-directory | path join client.log
}

def server-log-path []: nothing -> string {
    runtime-directory | path join server.log
}

def default-port []: nothing -> int {
    # Derive every worktree's default from its absolute path instead of using a
    # well-known main-worktree port that can collide with another project.
    let prefix = worktree-id | str substring 0..3 | into int --radix 16
    $WORKTREE_PORT_BASE + ($prefix mod $WORKTREE_PORT_SPAN)
}

def configured-port []: nothing -> int {
    let state = if (session-state-path | path exists) {
        try { open (session-state-path) } catch { null }
    } else {
        null
    }
    $state.port? | default (default-port) | into int
}

def prepare-runtime-directory [] {
    let directory = runtime-directory
    mkdir $directory
    ^chmod 700 $directory
}

def --wrapped client-result [...arguments: string]: nothing -> record {
    ^process-compose --use-uds --unix-socket (socket-path) --log-file (client-log-path) ...$arguments | complete
}

def require-session [] {
    if (client-result process list --output json).exit_code != 0 {
        error make {msg: "No Zhongdou Sans Panoptor session is running.", help: "Run `nur panoptor start`."}
    }
}

def process-state [role: string]: nothing -> string {
    let listing = client-result process list --output json
    if $listing.exit_code != 0 {
        error make {msg: "Could not read Panoptor process state.", help: ($listing.stderr | str trim)}
    }
    let processes = try { $listing.stdout | from json } catch {
        error make {msg: "Process Compose returned invalid JSON process state."}
    }
    let process = $processes | where name == $role | get --optional 0
    if $process == null {
        error make {msg: $"Unknown Panoptor role '($role)'.", help: "Run `nur panoptor list`."}
    }
    $process.status? | default unknown | into string | str lowercase
}

def run-role-action [action: string role: string] {
    require-session
    let actual_action = if $action == rerun {
        let state = process-state $role
        if $state in [running ready launching pending] { "restart" } else { "start" }
    } else {
        $action
    }
    if $actual_action not-in [start stop restart] {
        error make {msg: "Role action must be 'start', 'stop', 'restart', or 'rerun'."}
    }
    let result = client-result process $actual_action $role
    if $result.exit_code != 0 {
        error make {msg: $"Could not ($actual_action) Panoptor role '($role)'.", help: (($result.stdout + $result.stderr) | str trim)}
    }
    print $"($role): ($actual_action) requested."
}

def port-available [port: int]: nothing -> bool {
    let script = "import socket, sys; s = socket.socket(); s.bind(('127.0.0.1', int(sys.argv[1]))); s.close()"
    (^python -c $script ($port | into string) | complete).exit_code == 0
}

def start-panoptor [port?: int] {
    prepare-runtime-directory
    let socket = socket-path
    if (client-result process list --output json).exit_code == 0 {
        error make {msg: "Zhongdou Sans Panoptor is already running.", help: "Run `nur panoptor list` or `nur panoptor attach`."}
    }
    let selected_port = $port | default (default-port)
    if not (port-available $selected_port) {
        error make {msg: $"Port ($selected_port) is unavailable.", help: "Choose another port with `nur panoptor start --port <port>`."}
    }
    if ($socket | path exists) {
        rm --force $socket
    }
    {
        project: $PROJECT_NAME
        worktree: (repository-root)
        worktree_id: (worktree-id)
        port: $selected_port
        socket: $socket
    } | save --force (session-state-path)
    let started = with-env {
        PANOPTOR_PROJECT_ROOT: (repository-root)
        PANOPTOR_SITE_PORT: ($selected_port | into string)
    } {
        ^process-compose --use-uds --unix-socket $socket --log-file (server-log-path) --ordered-shutdown up --config $CONFIG_PATH --detached --tui=false --disable-dotenv --keep-project | complete
    }
    if $started.exit_code != 0 {
        error make {msg: "Process Compose could not start Zhongdou Sans Panoptor.", help: (($started.stdout + $started.stderr) | str trim)}
    }
    for _ in 1..40 {
        if (client-result process list --output json).exit_code == 0 {
            print $"Zhongdou Sans Panoptor started for worktree (worktree-id) on port ($selected_port)."
            return
        }
        sleep 250ms
    }
    error make {msg: "Panoptor did not open its control socket.", help: $"Inspect (server-log-path)."}
}

def stop-panoptor [] {
    require-session
    let stopped = client-result down
    if $stopped.exit_code != 0 {
        error make {msg: "Process Compose could not stop Zhongdou Sans Panoptor.", help: (($stopped.stdout + $stopped.stderr) | str trim)}
    }
    print "Zhongdou Sans Panoptor stopped."
}

# Validate the checked-in graph without starting its roles.
export def "nur panoptor check" [--port: int] {
    let selected_port = $port | default (default-port)
    with-env {
        PANOPTOR_PROJECT_ROOT: (repository-root)
        PANOPTOR_SITE_PORT: ($selected_port | into string)
    } {
        ^process-compose up --config $CONFIG_PATH --dry-run --disable-dotenv --tui=false
    }
}

# Start this worktree's complete topology headlessly.
export def "nur panoptor start" [--port: int] {
    start-panoptor $port
}

# Stop this worktree's roles and Process Compose server.
export def "nur panoptor stop" [] {
    stop-panoptor
}

# Attach the TUI without changing the session lifecycle.
export def "nur panoptor attach" [] {
    prepare-runtime-directory
    require-session
    ^process-compose --use-uds --unix-socket (socket-path) --log-file (client-log-path) attach
}

# List role liveness and readiness, optionally as JSON.
export def "nur panoptor list" [--json] {
    prepare-runtime-directory
    require-session
    let output = if $json { "json" } else { "wide" }
    ^process-compose --use-uds --unix-socket (socket-path) --log-file (client-log-path) process list --output $output
}

# Print a bounded tail from one role's log buffer.
export def "nur panoptor output" [role: string --tail: int = 100] {
    prepare-runtime-directory
    require-session
    if $tail < 1 {
        error make {msg: "--tail must be a positive line count."}
    }
    ^process-compose --use-uds --unix-socket (socket-path) --log-file (client-log-path) process logs $role --tail $tail
}

# Start, stop, restart, or freshly rerun one role.
export def "nur panoptor role" [action: string role: string] {
    prepare-runtime-directory
    run-role-action $action $role
}

# Recover one role, or restart the complete worktree topology on its prior port.
export def "nur panoptor recover" [role?: string] {
    prepare-runtime-directory
    if $role == null {
        let port = configured-port
        stop-panoptor
        start-panoptor $port
    } else {
        run-role-action rerun $role
    }
}
