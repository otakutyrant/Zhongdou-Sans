# nu-lint-ignore-file: unhandled_external_error
# Per-worktree Kitty session discovery, visibility, and interactive role control.

const PROJECT_ROOT = path self | path dirname | path dirname
const SESSION_FILE = $PROJECT_ROOT | path join tools panoptor.kitty-session
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
    runtime-directory | path join kitty.sock
}

def panoptor-address []: nothing -> string {
    $"unix:(socket-path)"
}

def session-state-path []: nothing -> string {
    runtime-directory | path join session.json
}

def role-config-path [role: string]: nothing -> string {
    runtime-directory | path join $"($role)-command.json"
}

def role-state-path [role: string]: nothing -> string {
    runtime-directory | path join $"($role)-role.json"
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
    let session = read-record (session-state-path)
    if $session == null {
        default-port
    } else {
        $session.port | into int
    }
}

def declared-roles [port: int]: nothing -> list<record> {
    [
        {
            name: site
            kind: server
            title: zhongdou-site
            command: [nur site watch --port ($port | into string)]
        }
        {
            name: checks
            kind: validation
            title: zhongdou-checks
            command: [nur check watch]
        }
    ]
}

def declared-role [role: string]: nothing -> record {
    let match = declared-roles (configured-port) | where name == $role
    if ($match | is-empty) {
        error make { msg: "Role must be `site` or `checks`." }
    }
    $match | first
}

def active-command [role: string]: nothing -> list<string> {
    let config = read-record (role-config-path $role)
    if $config == null {
        declared-role $role | get command
    } else {
        $config.active_command
    }
}

def save-active-command [role: string command: list<string>] {
    let declared = declared-role $role
    atomic-save (role-config-path $role) {
        role: $role
        declared_command: $declared.command
        active_command: $command
        updated_at: (now)
    }
}

def remote [arguments: list<string>]: nothing -> record {
    ^kitten @ --to (panoptor-address) ...$arguments | complete
}

def inventory []: nothing -> list<record> {
    let result = remote [ls]
    if $result.exit_code != 0 {
        return []
    }
    let tree = $result.stdout | from json
    mut windows = []
    for os_window in $tree {
        for tab in $os_window.tabs {
            for window in $tab.windows {
                $windows = $windows | append $window
            }
        }
    }
    $windows
}

def role-windows [role: string]: nothing -> list<record> {
    declared-role $role | ignore
    inventory | where {|window|
        ($window.user_vars?.panoptor_role? | default "") == $role
    }
}

def require-session [] {
    let result = remote [ls]
    if $result.exit_code != 0 {
        error make {
            msg: "Panoptor is stopped."
            help: "Run `nur panoptor start`."
        }
    }
}

def require-one-window [role: string]: nothing -> record {
    require-session
    let windows = role-windows $role
    if ($windows | length) != 1 {
        error make {
            msg: $"Expected one `($role)` pane, found ($windows | length)."
            help: $"Use `nur panoptor rerun ($role)` to restore its declared command."
        }
    }
    $windows | first
}

def pane-output-by-id [window_id: int lines: int]: nothing -> list<string> {
    let result = remote [
        get-text
        --match
        $"id:($window_id)"
        --extent
        all
    ]
    if $result.exit_code != 0 {
        return []
    }
    $result.stdout | lines | last $lines
}

def current-pane-output [lines: int]: nothing -> list<string> {
    let window_id = $env.KITTY_WINDOW_ID?
    if $window_id == null {
        return []
    }
    pane-output-by-id ($window_id | into int) $lines
}

def process-running [window: record]: nothing -> bool {
    ($window.env?.KITTY_HOLD? | default "") != "1"
}

def role-summary [role: record]: nothing -> record {
    let windows = role-windows $role.name
    let lifecycle = read-record (role-state-path $role.name)
    let config = read-record (role-config-path $role.name)
    let active = if $config == null { $role.command } else { $config.active_command }
    let latest_task = if $active == $role.command {
        read-record (task-state-path $role.name)
    } else {
        null
    }
    let window = if ($windows | is-empty) { null } else { $windows | first }
    let process_state = if $window == null {
        if $lifecycle != null and $lifecycle.state == "starting" {
            "starting"
        } else {
            "unknown"
        }
    } else if (process-running $window) {
        "running"
    } else if $lifecycle == null or $lifecycle.state == "running" {
        "unknown"
    } else {
        $lifecycle.state
    }
    let state = if $process_state == "running" and $latest_task != null and $latest_task.state == "failed" {
        "failed"
    } else {
        $process_state
    }
    {
        role: $role.name
        kind: $role.kind
        state: $state
        process_state: $process_state
        pid: (if $window == null { null } else { $window.pid })
        declared_command: $role.command
        active_command: $active
        lifecycle: $lifecycle
        latest_task: $latest_task
    }
}

def panoptor-status []: nothing -> record {
    let result = remote [ls]
    let session_state = if $result.exit_code == 0 { "running" } else { "stopped" }
    let roles = if $session_state == "running" {
        declared-roles (configured-port) | each {|role| role-summary $role }
    } else {
        declared-roles (configured-port) | each {|role|
            {
                role: $role.name
                kind: $role.kind
                state: "stopped"
                process_state: "stopped"
                pid: null
                declared_command: $role.command
                active_command: (active-command $role.name)
                lifecycle: null
                latest_task: null
            }
        }
    }
    {
        project: $PROJECT_NAME
        worktree: (repository-root)
        worktree_id: (worktree-id)
        session: $session_state
        socket: (socket-path)
        port: (configured-port)
        roles: $roles
    }
}

def port-available [port: int]: nothing -> bool {
    let script = "import socket, sys; s = socket.socket(); s.bind(('127.0.0.1', int(sys.argv[1]))); s.close()"
    let result = (^python -c $script ($port | into string) | complete)
    $result.exit_code == 0
}

def check-port [port: int] {
    if not (port-available $port) {
        error make {
            msg: $"Port ($port) is unavailable."
            help: "Choose another port with `nur panoptor start --port <port>`."
        }
    }
}

def wait-for-session [] {
    for _ in 1..40 {
        if (remote [ls]).exit_code == 0 {
            return
        }
        sleep 50ms
    }
    error make { msg: "Panoptor did not expose its Kitty control socket." }
}

def wait-for-shutdown [port: int] {
    for _ in 1..100 {
        if (remote [ls]).exit_code != 0 and (port-available $port) {
            return
        }
        sleep 50ms
    }
    error make {
        msg: "Panoptor did not release its control socket and site port in time."
        help: "Inspect the worktree's Kitty processes before starting it again."
    }
}

def owns-snapshot [role: string]: nothing -> bool {
    let window_id = $env.KITTY_WINDOW_ID? | default null
    let owner_socket = $env.PANOPTOR_SOCKET? | default ""
    let owner_worktree = $env.PANOPTOR_WORKTREE? | default ""
    if $window_id == null or $owner_socket != (socket-path) or $owner_worktree != (worktree-id) {
        return false
    }
    role-windows $role | any {|window|
        let id_matches = $window.id == ($window_id | into int)
        let owned_worktree = $window.user_vars?.panoptor_worktree? | default ""
        let worktree_matches = $owned_worktree == (worktree-id)
        $id_matches and $worktree_matches
    }
}

def run-streaming [command: list<string>]: nothing -> int {
    let executable = $command | first
    let arguments = $command | skip 1
    let result = try {
        ^$executable ...$arguments
        {exit_code: $env.LAST_EXIT_CODE error: null}
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

def launch-role [role: string command: list<string>] {
    require-session
    let definition = declared-role $role
    let old_windows = role-windows $role
    save-active-command $role $command
    let stale_task = task-state-path $role
    if ($stale_task | path exists) {
        rm $stale_task
    }
    let match_tab = $"window_title:^($definition.title)$"
    let result = remote [
        launch
        --match
        $match_tab
        --type
        window
        --location
        vsplit
        --cwd
        $PROJECT_ROOT
        --hold
        --title
        $definition.title
        --var
        $"panoptor_role=($role)"
        --var
        $"panoptor_worktree=(worktree-id)"
        nur
        panoptor
        role-run
        $role
    ]
    if $result.exit_code != 0 {
        error make { msg: ($result.stderr | str trim) }
    }
    for window in $old_windows {
        remote [close-window --match $"id:($window.id)"] | ignore
    }
}

def launch-held-role [role: string] {
    require-session
    let definition = declared-role $role
    let old_windows = role-windows $role
    let message = $"print 'Role `($role)` is stopped. Use `nur panoptor start-role ($role)`.'"
    let result = remote [
        launch
        --match
        $"window_title:^($definition.title)$"
        --type
        window
        --location
        vsplit
        --cwd
        $PROJECT_ROOT
        --hold
        --title
        $definition.title
        --var
        $"panoptor_role=($role)"
        --var
        $"panoptor_worktree=(worktree-id)"
        nu
        -c
        $message
    ]
    if $result.exit_code != 0 {
        error make { msg: ($result.stderr | str trim) }
    }
    for window in $old_windows {
        remote [close-window --match $"id:($window.id)"] | ignore
    }
    atomic-save (role-state-path $role) {
        role: $role
        kind: $definition.kind
        state: "completed"
        command: (active-command $role)
        started_at: null
        finished_at: (now)
        exit_code: 0
        diagnostics: [$"Role `($role)` was stopped by a Panoptor controller."]
    }
}

# Run one command while atomically publishing its latest Panoptor status.
export def run-with-panoptor-snapshot [role: string command: list<string>] {
    if not (owns-snapshot $role) {
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
        diagnostics: []
    }
    let exit_code = run-streaming $command
    atomic-save (task-state-path $role) {
        role: $role
        state: (if $exit_code == 0 { "completed" } else { "failed" })
        command: $command
        started_at: $started_at
        finished_at: (now)
        exit_code: $exit_code
        diagnostics: (current-pane-output 80)
    }
    if $exit_code != 0 {
        exit $exit_code
    }
}

# Run the active command for one pane and record its lifecycle for controllers.
export def "nur panoptor role-run" [role: string] {
    let definition = declared-role $role
    let command = active-command $role
    let window_id = $env.KITTY_WINDOW_ID? | default null
    if $window_id != null {
        remote [
            set-user-vars
            --match
            $"id:($window_id)"
            $"panoptor_worktree=(worktree-id)"
        ] | ignore
    }
    let started_at = now
    atomic-save (role-state-path $role) {
        role: $role
        kind: $definition.kind
        state: "running"
        command: $command
        started_at: $started_at
        finished_at: null
        exit_code: null
        diagnostics: []
    }
    let exit_code = run-streaming $command
    atomic-save (role-state-path $role) {
        role: $role
        kind: $definition.kind
        state: (if $exit_code == 0 { "completed" } else { "failed" })
        command: $command
        started_at: $started_at
        finished_at: (now)
        exit_code: $exit_code
        diagnostics: (current-pane-output 80)
    }
    if $exit_code != 0 {
        exit $exit_code
    }
}

# Start this worktree's isolated Panoptor session without displaying a window.
export def "nur panoptor start" [--port: int] {
    if (remote [ls]).exit_code == 0 {
        error make { msg: "Panoptor is already running. Use `nur panoptor status`." }
    }
    let selected_port = $port | default (default-port)
    check-port $selected_port
    mkdir (runtime-directory)
    atomic-save (session-state-path) {
        project: $PROJECT_NAME
        worktree: (repository-root)
        worktree_id: (worktree-id)
        port: $selected_port
        socket: (socket-path)
        started_at: (now)
    }
    for role in (declared-roles $selected_port) {
        save-active-command $role.name $role.command
        let stale_task = task-state-path $role.name
        if ($stale_task | path exists) {
            rm $stale_task
        }
        atomic-save (role-state-path $role.name) {
            role: $role.name
            kind: $role.kind
            state: "starting"
            command: $role.command
            started_at: (now)
            finished_at: null
            exit_code: null
            diagnostics: []
        }
    }
    let kitty_arguments = [
        --detach
        --directory
        $PROJECT_ROOT
        --listen-on
        (panoptor-address)
        --override
        allow_remote_control=socket-only
        --session
        $SESSION_FILE
    ]
    with-env {
        PANOPTOR_SOCKET: (socket-path)
        PANOPTOR_WORKTREE: (worktree-id)
    } {
        ^kitty ...$kitty_arguments
    }
    wait-for-session
    # Initializing the Wayland surface before hiding it avoids a Kitty crash when
    # an initially hidden surface is first shown on some compositors.
    remote [resize-os-window --match all --action hide --no-response] | ignore
    print $"Started hidden Panoptor session `(worktree-id)` on port ($selected_port)."
}

# Report session and per-role state; pair --json with Nur's --quiet flag.
export def "nur panoptor status" [--json] {
    let status = panoptor-status
    if $json {
        $status | to json | print
    } else {
        print $"Panoptor session: ($status.session)"
        print $"Worktree: ($status.worktree_id)  Site port: ($status.port)"
        $status.roles
            | select role kind state process_state pid active_command
            | table
            | print
    }
}

# Show the existing Panoptor session without restarting any role.
export def "nur panoptor show" [] {
    require-session
    let result = remote [resize-os-window --match all --action show --no-response]
    if $result.exit_code != 0 {
        error make { msg: ($result.stderr | str trim) }
    }
}

# Hide the Panoptor session while keeping every role alive.
export def "nur panoptor hide" [] {
    require-session
    let result = remote [resize-os-window --match all --action hide --no-response]
    if $result.exit_code != 0 {
        error make { msg: ($result.stderr | str trim) }
    }
}

# Toggle the existing Panoptor session's visibility without restarting roles.
export def "nur panoptor toggle" [] {
    require-session
    let result = remote [resize-os-window --match all --action toggle-visibility --no-response]
    if $result.exit_code != 0 {
        error make { msg: ($result.stderr | str trim) }
    }
}

# Read bounded recent output from one role without entering Kitty.
export def "nur panoptor inspect" [role: string --lines: int = 80] {
    let window = require-one-window $role
    pane-output-by-id $window.id $lines | str join (char newline) | print
}

# Send literal input to a role, optionally followed by Enter.
export def "nur panoptor send" [role: string text: string --enter] {
    let window = require-one-window $role
    $text | ^kitten @ --to (panoptor-address) send-text --match $"id:($window.id)" --stdin
    if $enter {
        let result = remote [send-key --match $"id:($window.id)" enter]
        if $result.exit_code != 0 {
            error make { msg: ($result.stderr | str trim) }
        }
    }
}

# Send SIGINT to the foreground process in one role.
export def "nur panoptor interrupt" [role: string] {
    let window = require-one-window $role
    let result = remote [signal-child --match $"id:($window.id)" SIGINT]
    if $result.exit_code != 0 {
        error make { msg: ($result.stderr | str trim) }
    }
}

# Launch an absent or held role with its current session command.
export def "nur panoptor start-role" [role: string] {
    let windows = role-windows $role
    if not ($windows | is-empty) and (process-running ($windows | first)) {
        error make { msg: $"Role `($role)` is already running." }
    }
    launch-role $role (active-command $role)
}

# Stop one role and keep its held pane available for inspection.
export def "nur panoptor stop-role" [role: string] {
    launch-held-role $role
}

# Restart one role with its current session command.
export def "nur panoptor restart" [role: string] {
    launch-held-role $role
    launch-role $role (active-command $role)
}

# Restore and launch one role's declared command.
export def "nur panoptor rerun" [role: string] {
    let declared = declared-role $role | get command
    let windows = role-windows $role
    if not ($windows | is-empty) and (process-running ($windows | first)) {
        launch-held-role $role
    }
    save-active-command $role $declared
    launch-role $role $declared
}

# Replace one role with an arbitrary session-only diagnostic command.
export def "nur panoptor replace" [role: string command: string ...arguments: string] {
    let replacement = [$command ...$arguments]
    let windows = role-windows $role
    if not ($windows | is-empty) and (process-running ($windows | first)) {
        launch-held-role $role
    }
    save-active-command $role $replacement
    launch-role $role $replacement
}

# Stop only this worktree's Panoptor session and all of its roles.
export def "nur panoptor stop" [] {
    require-session
    let port = configured-port
    let result = remote [close-window --match all]
    if $result.exit_code != 0 {
        error make { msg: ($result.stderr | str trim) }
    }
    wait-for-shutdown $port
}
