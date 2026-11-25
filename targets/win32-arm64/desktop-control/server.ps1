# An MCP server on standard input and output that takes pictures of the
# screen and sends mouse and keyboard input. Windows only; it needs nothing
# beyond Windows PowerShell and the system's own libraries.
#
# The tools are described in tools.json beside this file, which the macOS and
# Linux versions read as well, so all three offer the same tools.
$ErrorActionPreference = 'Stop'
$Version = '0.3.4'
# The longest edge of a picture handed back, in pixels.
$Longest = 1568
$Subject = "the user's computer"

$utf8 = New-Object System.Text.UTF8Encoding $false
[Console]::InputEncoding = $utf8
[Console]::OutputEncoding = $utf8

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;

public class WindowEntry {
    public long Id; public int Pid; public string Title; public bool Focused;
    public int Left; public int Top; public int Right; public int Bottom;
}

public static class DesktopInput {
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X; public int Y; }
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }

    [DllImport("user32.dll")] static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] static extern bool SetProcessDpiAwarenessContext(IntPtr value);
    [DllImport("shcore.dll")] static extern int SetProcessDpiAwareness(int value);
    [DllImport("shcore.dll")] static extern int GetDpiForMonitor(IntPtr monitor, int type, out uint x, out uint y);
    [DllImport("user32.dll")] static extern IntPtr MonitorFromPoint(POINT point, uint flags);
    [DllImport("user32.dll", SetLastError = true)] static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll", SetLastError = true)] static extern bool GetCursorPos(out POINT point);
    [DllImport("user32.dll", SetLastError = true)] static extern uint SendInput(uint count, INPUT[] inputs, int size);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern short VkKeyScanW(char c);

    delegate bool EnumProc(IntPtr window, IntPtr data);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc proc, IntPtr data);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr window);
    [DllImport("user32.dll")] static extern bool IsIconic(IntPtr window);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowLong(IntPtr window, int index);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowTextLength(IntPtr window);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr window, StringBuilder text, int most);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr window, StringBuilder text, int most);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr window, out uint process);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr window, out RECT rect);
    [DllImport("dwmapi.dll")] static extern int DwmGetWindowAttribute(IntPtr window, int attribute, out RECT value, int size);
    [DllImport("dwmapi.dll")] static extern int DwmGetWindowAttribute(IntPtr window, int attribute, out int value, int size);

    [StructLayout(LayoutKind.Sequential)]
    struct MOUSEINPUT { public int dx; public int dy; public uint mouseData; public uint dwFlags; public uint time; public IntPtr extra; }
    [StructLayout(LayoutKind.Sequential)]
    struct KEYBDINPUT { public ushort wVk; public ushort wScan; public uint dwFlags; public uint time; public IntPtr extra; }
    [StructLayout(LayoutKind.Explicit)]
    struct INPUTUNION { [FieldOffset(0)] public MOUSEINPUT mi; [FieldOffset(0)] public KEYBDINPUT ki; }
    [StructLayout(LayoutKind.Sequential)]
    struct INPUT { public uint type; public INPUTUNION u; }

    const uint KEYUP = 0x2, UNICODE = 0x4, EXTENDED = 0x1;
    const int EXSTYLE = -20, TOOLWINDOW = 0x80, APPWINDOW = 0x40000, CLOAKED = 14, FRAME_BOUNDS = 9;

    // Pictures and positions in the screen's own pixels, whatever the
    // display scaling: per-monitor aware where Windows offers it.
    public static void Aware() {
        try { if (SetProcessDpiAwarenessContext(new IntPtr(-4))) return; } catch (EntryPointNotFoundException) { }
        try { if (SetProcessDpiAwareness(2) == 0) return; } catch (DllNotFoundException) { } catch (EntryPointNotFoundException) { }
        SetProcessDPIAware();
    }

    // The display's scaling factor, 1 at 100%.
    public static double Scale(int x, int y) {
        try {
            POINT point; point.X = x; point.Y = y;
            uint dx, dy;
            if (GetDpiForMonitor(MonitorFromPoint(point, 2), 0, out dx, out dy) == 0 && dx > 0) return dx / 96.0;
        } catch (DllNotFoundException) { } catch (EntryPointNotFoundException) { }
        return 1.0;
    }

    static void Send(INPUT[] inputs) {
        uint sent = SendInput((uint)inputs.Length, inputs, Marshal.SizeOf(typeof(INPUT)));
        if (sent != inputs.Length) throw new Win32Exception(Marshal.GetLastWin32Error(), "Windows did not accept the input");
    }

    public static void MoveTo(int x, int y) {
        if (!SetCursorPos(x, y)) throw new Win32Exception(Marshal.GetLastWin32Error(), "Windows did not move the pointer");
    }

    public static int[] Cursor() {
        POINT point;
        if (!GetCursorPos(out point)) throw new Win32Exception(Marshal.GetLastWin32Error(), "Windows did not tell where the pointer is");
        return new int[] { point.X, point.Y };
    }

    public static void Mouse(uint flags, int data) {
        INPUT[] input = new INPUT[1];
        input[0].type = 0;
        input[0].u.mi.dwFlags = flags;
        input[0].u.mi.mouseData = unchecked((uint)data);
        Send(input);
    }

    public static void Key(ushort vk, bool up, bool extended) {
        INPUT[] input = new INPUT[1];
        input[0].type = 1;
        input[0].u.ki.wVk = vk;
        input[0].u.ki.dwFlags = (up ? KEYUP : 0) | (extended ? EXTENDED : 0);
        Send(input);
    }

    // The key and shift state that type a character on the active layout,
    // or -1 when no key does.
    public static int KeyScan(char c) { return VkKeyScanW(c); }

    // Each character as itself, not as keys of a layout, so the active input
    // method and keyboard layout do not change it. Control characters are
    // left out; line breaks and tabs are pressed as keys by the caller.
    public static void Text(string text) {
        foreach (char c in text) {
            if (c < 0x20 || (c >= 0x7F && c < 0xA0)) continue;
            INPUT[] input = new INPUT[2];
            input[0].type = input[1].type = 1;
            input[0].u.ki.wScan = input[1].u.ki.wScan = c;
            input[0].u.ki.dwFlags = UNICODE;
            input[1].u.ki.dwFlags = UNICODE | KEYUP;
            Send(input);
            System.Threading.Thread.Sleep(2);
        }
    }

    // The visible top-level windows, front to back.
    public static WindowEntry[] Windows() {
        List<WindowEntry> found = new List<WindowEntry>();
        IntPtr front = GetForegroundWindow();
        EnumProc each = delegate (IntPtr window, IntPtr data) {
            if (!IsWindowVisible(window) || IsIconic(window)) return true;
            int style = GetWindowLong(window, EXSTYLE);
            if ((style & TOOLWINDOW) != 0 && (style & APPWINDOW) == 0) return true;
            int cloaked = 0;
            try { if (DwmGetWindowAttribute(window, CLOAKED, out cloaked, 4) == 0 && cloaked != 0) return true; } catch (DllNotFoundException) { }
            int length = GetWindowTextLength(window);
            if (length == 0) return true;
            StringBuilder title = new StringBuilder(length + 1);
            GetWindowText(window, title, title.Capacity);
            StringBuilder kind = new StringBuilder(256);
            GetClassName(window, kind, kind.Capacity);
            if (kind.ToString() == "Progman" || kind.ToString() == "WorkerW") return true;
            RECT rect;
            bool framed = false;
            try { framed = DwmGetWindowAttribute(window, FRAME_BOUNDS, out rect, Marshal.SizeOf(typeof(RECT))) == 0; } catch (DllNotFoundException) { rect = new RECT(); }
            if (!framed && !GetWindowRect(window, out rect)) return true;
            if (rect.Right - rect.Left < 2 || rect.Bottom - rect.Top < 2) return true;
            uint process;
            GetWindowThreadProcessId(window, out process);
            WindowEntry entry = new WindowEntry();
            entry.Id = window.ToInt64(); entry.Pid = (int)process; entry.Title = title.ToString(); entry.Focused = window == front;
            entry.Left = rect.Left; entry.Top = rect.Top; entry.Right = rect.Right; entry.Bottom = rect.Bottom;
            found.Add(entry);
            return true;
        };
        EnumWindows(each, IntPtr.Zero);
        GC.KeepAlive(each);
        return found.ToArray();
    }
}
'@

[DesktopInput]::Aware()
Add-Type -AssemblyName System.Drawing, System.Windows.Forms

# Mouse button flags for SendInput: down, up.
$ButtonFlags = @{ left = @(0x2, 0x4); right = @(0x8, 0x10); middle = @(0x20, 0x40) }
$ModifierCodes = @{
    # cmd and command mean the shortcut modifier, as mod does: ctrl here.
    ctrl = 0x11; control = 0x11; mod = 0x11; cmd = 0x11; command = 0x11; shift = 0x10; alt = 0x12; option = 0x12
    meta = 0x5B; win = 0x5B; windows = 0x5B; super = 0x5B
}
$KeyCodes = @{ return = 0x0D; enter = 0x0D; tab = 0x09; space = 0x20; backspace = 0x08; escape = 0x1B; esc = 0x1B }
# Keys outside the main block, which Windows tells apart by a flag.
$ExtendedCodes = @{
    delete = 0x2E; insert = 0x2D; left = 0x25; up = 0x26; right = 0x27; down = 0x28
    home = 0x24; end = 0x23; pageup = 0x21; pagedown = 0x22
}
for ($i = 1; $i -le 12; $i++) { $KeyCodes["f$i"] = 0x6F + $i }
# Lines per notch are the system's own: one notch is one wheel click.
$WheelDelta = 120

function Refuse([string]$message) { throw [System.ArgumentException]::new($message) }

function Test-Number($value) { return ($value -is [ValueType]) -and ($value -isnot [bool]) -and ($value -isnot [char]) }
function Test-Whole($value) { return ($value -is [int]) -or ($value -is [long]) }

# Displays and positions. A position is in pixels of the latest full
# screenshot of a display; what each screenshot covered is kept here, so
# positions keep meaning what the picture showed.
$script:Shots = @{}
$script:Held = New-Object System.Collections.Generic.List[string]

function Measure-Area([double]$wide, [double]$high) {
    $shrink = [Math]::Max(1.0, [Math]::Max($wide, $high) / $Longest)
    return @([int][Math]::Max(1, [Math]::Round($wide / $shrink)), [int][Math]::Max(1, [Math]::Round($high / $shrink)))
}

# The displays, main first, then from left to right.
function Get-Displays {
    $all = @([System.Windows.Forms.Screen]::AllScreens)
    $sorted = @($all | Sort-Object { $_.Bounds.X }, { $_.Bounds.Y })
    $main = @($sorted | Where-Object { $_.Primary } | Select-Object -First 1)
    if ($main.Count -eq 0) { $main = @($sorted[0]) }
    $ordered = @($main) + @($sorted | Where-Object { $_.DeviceName -ne $main[0].DeviceName })
    $list = @()
    foreach ($screen in $ordered) {
        $b = $screen.Bounds
        $list += , @{ X = $b.X; Y = $b.Y; Width = $b.Width; Height = $b.Height; Scale = [DesktopInput]::Scale($b.X + [int]($b.Width / 2), $b.Y + [int]($b.Height / 2)) }
    }
    return , $list
}

# What a full screenshot of a display covers: its area in pixels, and the picture's size.
function Get-Geometry([int]$number) {
    $displays = Get-Displays
    if ($number -lt 0 -or $number -ge $displays.Count) { Refuse "there is no display $number; list_displays shows the displays" }
    $d = $displays[$number]
    $size = Measure-Area $d.Width $d.Height
    return @{ X = $d.X; Y = $d.Y; Wide = $d.Width; High = $d.Height; Width = $size[0]; Height = $size[1] }
}

# The latest full screenshot of a display, or what one would cover now.
function Get-Shot([int]$number) {
    if ($script:Shots.ContainsKey($number)) { return $script:Shots[$number] }
    return Get-Geometry $number
}

function Get-DisplayNumber($arguments) {
    $number = $arguments.display
    if ($null -eq $number) { return 0 }
    if (-not (Test-Whole $number) -or $number -lt 0) { Refuse 'display must be a whole number, as list_displays shows' }
    return [int]$number
}

# A position given in pixels of a screenshot, in pixels of the screen.
function Get-Place($arguments, [string]$x = 'x', [string]$y = 'y') {
    $px = $arguments.$x; $py = $arguments.$y
    if (-not (Test-Number $px) -or -not (Test-Number $py)) { Refuse "$x and $y must be numbers, in pixels of the latest screenshot" }
    $s = Get-Shot (Get-DisplayNumber $arguments)
    if ([double]$px -lt 0 -or [double]$px -gt $s.Width -or [double]$py -lt 0 -or [double]$py -gt $s.Height) {
        Refuse "that position is outside the display, which is $($s.Width)x$($s.Height) pixels in its screenshot"
    }
    $sx = $s.X + [int][Math]::Round([double]$px * $s.Wide / $s.Width)
    $sy = $s.Y + [int][Math]::Round([double]$py * $s.High / $s.Height)
    return @([Math]::Min($sx, $s.X + $s.Wide - 1), [Math]::Min($sy, $s.Y + $s.High - 1))
}

# The display a point of the screen is on, and the point in pixels of its screenshot.
function Get-Where([int]$sx, [int]$sy) {
    $displays = Get-Displays
    $number = 0
    for ($n = 0; $n -lt $displays.Count; $n++) {
        $d = $displays[$n]
        if ($sx -ge $d.X -and $sx -lt $d.X + $d.Width -and $sy -ge $d.Y -and $sy -lt $d.Y + $d.Height) { $number = $n; break }
    }
    $s = Get-Shot $number
    return @($number, [int][Math]::Round(($sx - $s.X) * $s.Width / $s.Wide), [int][Math]::Round(($sy - $s.Y) * $s.Height / $s.High))
}

# The part of an area (x, y, width, height) inside bounds, or $null.
function Get-Clip($area, $bounds) {
    $left = [Math]::Max($area[0], $bounds[0]); $top = [Math]::Max($area[1], $bounds[1])
    $right = [Math]::Min($area[0] + $area[2], $bounds[0] + $bounds[2]); $bottom = [Math]::Min($area[1] + $area[3], $bounds[1] + $bounds[3])
    if ($right -le $left -or $bottom -le $top) { return $null }
    return @($left, $top, ($right - $left), ($bottom - $top))
}

# A JPEG of an area of the screen, in pixels, at most $Longest pixels on its longest side.
function Get-Capture([int]$x, [int]$y, [int]$wide, [int]$high) {
    $size = Measure-Area $wide $high
    $full = New-Object System.Drawing.Bitmap $wide, $high
    $small = New-Object System.Drawing.Bitmap $size[0], $size[1]
    $stream = New-Object System.IO.MemoryStream
    try {
        $graphics = [System.Drawing.Graphics]::FromImage($full)
        try { $graphics.CopyFromScreen($x, $y, 0, 0, (New-Object System.Drawing.Size $wide, $high)) }
        catch { Refuse 'The screen cannot be seen right now; it may be locked.' }
        finally { $graphics.Dispose() }
        $graphics = [System.Drawing.Graphics]::FromImage($small)
        $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $graphics.DrawImage($full, 0, 0, $size[0], $size[1])
        $graphics.Dispose()
        $codec = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object { $_.MimeType -eq 'image/jpeg' }
        $parameters = New-Object System.Drawing.Imaging.EncoderParameters 1
        $parameters.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter ([System.Drawing.Imaging.Encoder]::Quality, [long]80)
        $small.Save($stream, $codec, $parameters)
        $data = [Convert]::ToBase64String($stream.ToArray())
    } finally { $full.Dispose(); $small.Dispose(); $stream.Dispose() }
    return @{ Data = $data; Width = $size[0]; Height = $size[1] }
}

# The visible windows, front to back, in pixels of their display's screenshot.
function Get-WindowList {
    $displays = Get-Displays
    $list = @()
    foreach ($w in [DesktopInput]::Windows()) {
        $area = @($w.Left, $w.Top, ($w.Right - $w.Left), ($w.Bottom - $w.Top))
        $best = 0; $number = 0
        for ($n = 0; $n -lt $displays.Count; $n++) {
            $d = $displays[$n]
            $part = Get-Clip $area @($d.X, $d.Y, $d.Width, $d.Height)
            if ($null -ne $part -and $part[2] * $part[3] -gt $best) { $best = $part[2] * $part[3]; $number = $n }
        }
        if ($best -eq 0) { continue }  # wholly off every display
        $s = Get-Shot $number
        $app = ''
        try { $app = [System.Diagnostics.Process]::GetProcessById($w.Pid).ProcessName } catch { }
        $list += , ([ordered]@{
            id = $w.Id; app = $app; title = $w.Title; display = $number
            x = [int][Math]::Round(($area[0] - $s.X) * $s.Width / $s.Wide); y = [int][Math]::Round(($area[1] - $s.Y) * $s.Height / $s.High)
            width = [int][Math]::Round($area[2] * $s.Width / $s.Wide); height = [int][Math]::Round($area[3] * $s.Height / $s.High)
            focused = $w.Focused
        })
    }
    return , $list
}

function Get-RegionOf($arguments) {
    $region = $arguments.region
    $values = @()
    foreach ($key in @('x', 'y', 'width', 'height')) {
        $value = $region.$key
        if (-not (Test-Number $value)) { Refuse 'region needs x, y, width and height, numbers in pixels of the latest full screenshot' }
        $values += [double]$value
    }
    if ($values[2] -le 0 -or $values[3] -le 0) { Refuse 'region needs a width and height above 0' }
    return , $values
}

function Invoke-Screenshot($arguments) {
    if ($null -ne $arguments.region -and $null -ne $arguments.window) { Refuse 'give region or window, not both' }
    if ($null -ne $arguments.window) {
        $window = $arguments.window
        $entry = $null
        if (Test-Whole $window) { $entry = @(Get-WindowList) | Where-Object { $_.id -eq [long]$window } | Select-Object -First 1 }
        if ($null -eq $entry) { Refuse 'there is no such window; list_windows shows the windows and their ids' }
        $number = $entry.display
        $area = @($entry.x, $entry.y, $entry.width, $entry.height)
        $label = "Window $window on display $number"
    } elseif ($null -ne $arguments.region) {
        $number = Get-DisplayNumber $arguments
        $null = Get-Shot $number
        $area = Get-RegionOf $arguments
        $label = "Display $number, region"
    } else {
        $number = Get-DisplayNumber $arguments
        $s = Get-Geometry $number
        $picture = Get-Capture $s.X $s.Y $s.Wide $s.High
        $s.Width = $picture.Width; $s.Height = $picture.Height
        $script:Shots[$number] = $s
        return @(
            @{ type = 'image'; data = $picture.Data; mimeType = 'image/jpeg' },
            @{ type = 'text'; text = "Display ${number}: $($s.Width)x$($s.Height) pixels, showing the area of $($s.Wide)x$($s.High) at ($($s.X), $($s.Y)) in desktop coordinates. Positions for the other tools on display $number are pixels of this picture." }
        )
    }
    $s = Get-Shot $number
    $scaleX = $s.Wide / $s.Width; $scaleY = $s.High / $s.Height
    $wanted = @(($s.X + [Math]::Round($area[0] * $scaleX)), ($s.Y + [Math]::Round($area[1] * $scaleY)), [Math]::Round($area[2] * $scaleX), [Math]::Round($area[3] * $scaleY))
    $part = Get-Clip $wanted @($s.X, $s.Y, $s.Wide, $s.High)
    if ($null -eq $part) { Refuse "that area is outside display $number, which is $($s.Width)x$($s.Height) pixels in its screenshot" }
    $picture = Get-Capture $part[0] $part[1] $part[2] $part[3]
    $ax = [int][Math]::Round(($part[0] - $s.X) / $scaleX); $ay = [int][Math]::Round(($part[1] - $s.Y) / $scaleY)
    $aw = [int][Math]::Round($part[2] / $scaleX); $ah = [int][Math]::Round($part[3] / $scaleY)
    return @(
        @{ type = 'image'; data = $picture.Data; mimeType = 'image/jpeg' },
        @{ type = 'text'; text = "${label}: the area at ($ax, $ay) of ${aw}x$ah pixels of the latest full screenshot, shown at $($picture.Width)x$($picture.Height) pixels. This picture is only for looking closer: positions for the other tools stay pixels of the full screenshot of display $number ($($s.Width)x$($s.Height))." }
    )
}

function Invoke-ListDisplays($arguments) {
    $displays = Get-Displays
    $list = @()
    for ($n = 0; $n -lt $displays.Count; $n++) {
        $d = $displays[$n]
        $size = Measure-Area $d.Width $d.Height
        $list += , ([ordered]@{ display = $n; main = ($n -eq 0); x = $d.X; y = $d.Y; width = $d.Width; height = $d.Height
                                scale = [Math]::Round($d.Scale, 2); screenshot_width = $size[0]; screenshot_height = $size[1] })
    }
    return (ConvertTo-Json -InputObject ([ordered]@{ displays = @($list) }) -Depth 5 -Compress)
}

function Invoke-ListWindows($arguments) {
    return (ConvertTo-Json -InputObject ([ordered]@{ windows = @(Get-WindowList) }) -Depth 5 -Compress)
}

function Invoke-CursorPosition($arguments) {
    $at = [DesktopInput]::Cursor()
    $spot = Get-Where $at[0] $at[1]
    return (ConvertTo-Json -InputObject ([ordered]@{ display = $spot[0]; x = $spot[1]; y = $spot[2] }) -Compress)
}

function Get-Button($arguments) {
    $button = if ($null -eq $arguments.button) { 'left' } else { [string]$arguments.button }
    if (-not $ButtonFlags.ContainsKey($button)) { Refuse 'button is left, right or middle' }
    return $button
}

function Get-ModifierCodes($names) {
    $held = @()
    foreach ($name in $names) {
        $code = $ModifierCodes[$name]
        if ($held -notcontains $code) { $held += $code }
    }
    return , $held
}

function Get-ModifierNames($arguments) {
    $names = $arguments.modifiers
    if ($null -eq $names) { return , @() }
    if ($names -isnot [array] -or @($names | Where-Object { $_ -isnot [string] }).Count -gt 0) { Refuse 'modifiers is a list of modifier names, such as ["shift"]' }
    $lowered = @()
    foreach ($name in $names) {
        $name = $name.ToLowerInvariant()
        if (-not $ModifierCodes.ContainsKey($name)) { Refuse "unknown modifier $name; use ctrl, shift, alt, meta or mod" }
        $lowered += $name
    }
    return , $lowered
}

function Send-Modifiers($held, [bool]$up) {
    $order = @($held)
    if ($up) { [array]::Reverse($order) }
    foreach ($code in $order) { [DesktopInput]::Key($code, $up, $code -eq 0x5B) }
}

function Invoke-Move($arguments) {
    $at = Get-Place $arguments
    [DesktopInput]::MoveTo($at[0], $at[1])
    return 'moved'
}

function Invoke-Click($arguments) {
    $button = Get-Button $arguments
    $count = if ($null -eq $arguments.count) { 1 } else { $arguments.count }
    if (-not (Test-Whole $count) -or @(1, 2, 3) -notcontains $count) { Refuse 'count is 1, 2 or 3' }
    $held = Get-ModifierCodes (Get-ModifierNames $arguments)
    $at = Get-Place $arguments
    [DesktopInput]::MoveTo($at[0], $at[1])
    Start-Sleep -Milliseconds 50
    Send-Modifiers $held $false
    try {
        for ($press = 0; $press -lt $count; $press++) {
            [DesktopInput]::Mouse($ButtonFlags[$button][0], 0)
            Start-Sleep -Milliseconds 20
            [DesktopInput]::Mouse($ButtonFlags[$button][1], 0)
            Start-Sleep -Milliseconds 20
        }
    } finally { Send-Modifiers $held $true }
    return 'clicked'
}

function Invoke-Drag($arguments) {
    $button = Get-Button $arguments
    $start = Get-Place $arguments 'from_x' 'from_y'
    $end = Get-Place $arguments 'to_x' 'to_y'
    [DesktopInput]::MoveTo($start[0], $start[1])
    Start-Sleep -Milliseconds 50
    [DesktopInput]::Mouse($ButtonFlags[$button][0], 0)
    try {
        for ($step = 1; $step -le 10; $step++) {
            Start-Sleep -Milliseconds 20
            [DesktopInput]::MoveTo([int]($start[0] + ($end[0] - $start[0]) * $step / 10), [int]($start[1] + ($end[1] - $start[1]) * $step / 10))
        }
        Start-Sleep -Milliseconds 50
    } finally { [DesktopInput]::Mouse($ButtonFlags[$button][1], 0) }
    return 'dragged'
}

function Invoke-MouseDown($arguments) {
    $button = Get-Button $arguments
    [DesktopInput]::Mouse($ButtonFlags[$button][0], 0)
    if (-not $script:Held.Contains($button)) { $script:Held.Add($button) }
    return "holding the $button button"
}

function Invoke-MouseUp($arguments) {
    $button = Get-Button $arguments
    [DesktopInput]::Mouse($ButtonFlags[$button][1], 0)
    $null = $script:Held.Remove($button)
    return "let go of the $button button"
}

function Invoke-Scroll($arguments) {
    $down = if ($null -eq $arguments.down) { 0 } else { $arguments.down }
    $right = if ($null -eq $arguments.right) { 0 } else { $arguments.right }
    if (-not (Test-Whole $down) -or -not (Test-Whole $right)) { Refuse 'down and right must be whole numbers of wheel notches' }
    if ([Math]::Abs($down) -gt 100 -or [Math]::Abs($right) -gt 100 -or ($down -eq 0 -and $right -eq 0)) { Refuse 'give down or right, between -100 and 100 wheel notches' }
    $at = Get-Place $arguments
    [DesktopInput]::MoveTo($at[0], $at[1])
    Start-Sleep -Milliseconds 50
    # One wheel click a notch; mouse wheel data is positive away from the user.
    for ($i = 0; $i -lt [Math]::Abs($down); $i++) {
        [DesktopInput]::Mouse(0x0800, $(if ($down -gt 0) { -$WheelDelta } else { $WheelDelta }))
        Start-Sleep -Milliseconds 10
    }
    for ($i = 0; $i -lt [Math]::Abs($right); $i++) {
        [DesktopInput]::Mouse(0x1000, $(if ($right -gt 0) { $WheelDelta } else { -$WheelDelta }))
        Start-Sleep -Milliseconds 10
    }
    return 'scrolled'
}

function Send-Key([int]$code, [bool]$extended = $false) {
    [DesktopInput]::Key($code, $false, $extended)
    Start-Sleep -Milliseconds 20
    [DesktopInput]::Key($code, $true, $extended)
}

function Invoke-Type($arguments) {
    $text = $arguments.text
    if ($text -isnot [string] -or $text.Length -eq 0 -or $text.Length -gt 5000) { Refuse 'text must be 1 to 5000 characters' }
    $text = $text.Replace("`r`n", "`n").Replace("`r", "`n")
    foreach ($part in $text -split '([\n\t])') {
        if ($part -eq "`n") { Send-Key 0x0D }
        elseif ($part -eq "`t") { Send-Key 0x09 }
        elseif ($part.Length -gt 0) { [DesktopInput]::Text($part) }
    }
    return 'typed'
}

# Modifier names and the key of a combination such as ctrl+shift+a or ctrl++.
function Split-Keys([string]$keys) {
    $keys = $keys.ToLowerInvariant()
    if ($keys -eq '+') { return @(@(), '+') }
    if ($keys.EndsWith('++')) { return @(@($keys.Substring(0, $keys.Length - 2).Split('+') | Where-Object { $_ }), '+') }
    $names = $keys.Split('+')
    if ($names.Count -eq 1) { return @(@(), $names[0]) }
    return @(@($names[0..($names.Count - 2)]), $names[-1])
}

function Invoke-Key($arguments) {
    $keys = $arguments.keys
    if ($keys -isnot [string] -or $keys.Length -eq 0) { Refuse 'keys is a key, or modifiers and a key joined by +, such as mod+c' }
    $split = Split-Keys $keys
    $names = @($split[0]); $last = $split[1]
    foreach ($name in $names) {
        if (-not $ModifierCodes.ContainsKey($name)) { Refuse "unknown modifier $name; use ctrl, shift, alt, meta or mod" }
    }
    $held = Get-ModifierCodes $names
    $extended = $false
    if ($KeyCodes.ContainsKey($last)) { $code = $KeyCodes[$last] }
    elseif ($ExtendedCodes.ContainsKey($last)) { $code = $ExtendedCodes[$last]; $extended = $true }
    elseif ($last.Length -eq 1 -and [int][char]$last -ge 0x20) {
        $scan = [DesktopInput]::KeyScan([char]$last)
        if ($scan -eq -1 -or ($scan -band 0xFF) -eq 0xFF) {
            # A character no key of the layout has: typed as itself.
            if ($names.Count -gt 0) { Refuse "unknown key $last" }
            [DesktopInput]::Text($last)
            return 'pressed'
        }
        $code = $scan -band 0xFF
        $state = ($scan -shr 8) -band 0xFF
        foreach ($pair in @(@(1, 0x10), @(2, 0x11), @(4, 0x12))) {
            if (($state -band $pair[0]) -and $held -notcontains $pair[1]) { $held += $pair[1] }
        }
    }
    else { Refuse "unknown key $last" }
    Send-Modifiers $held $false
    try { Send-Key $code $extended }
    finally { Send-Modifiers $held $true }
    return 'pressed'
}

function Invoke-Wait($arguments) {
    $seconds = $arguments.seconds
    if (-not (Test-Number $seconds) -or [double]$seconds -lt 0 -or [double]$seconds -gt 30) { Refuse 'seconds is a number from 0 to 30' }
    Start-Sleep -Milliseconds ([int]([double]$seconds * 1000))
    return 'done waiting'
}

$Handlers = @{
    screenshot = 'Invoke-Screenshot'; list_displays = 'Invoke-ListDisplays'; list_windows = 'Invoke-ListWindows'
    cursor_position = 'Invoke-CursorPosition'; click = 'Invoke-Click'; move_pointer = 'Invoke-Move'; drag = 'Invoke-Drag'
    mouse_down = 'Invoke-MouseDown'; mouse_up = 'Invoke-MouseUp'; scroll = 'Invoke-Scroll'; type_text = 'Invoke-Type'
    press_key = 'Invoke-Key'; wait = 'Invoke-Wait'
}
$ToolText = [System.IO.File]::ReadAllText((Join-Path $PSScriptRoot 'tools.json'), $utf8).Replace('{computer}', $Subject)
$Tools = (ConvertFrom-Json -InputObject $ToolText).tools

function Get-Answer($message) {
    switch ($message.method) {
        'initialize' {
            return @{ protocolVersion = $message.params.protocolVersion; capabilities = @{ tools = @{} }
                      serverInfo = @{ name = 'desktop-control'; version = $Version } }
        }
        'tools/list' { return @{ tools = @($Tools) } }
        'tools/call' {
            $name = [string]$message.params.name
            if (-not $Handlers.ContainsKey($name)) { return $null }
            $arguments = if ($null -eq $message.params.arguments) { [pscustomobject]@{} } else { $message.params.arguments }
            try {
                $result = & $Handlers[$name] $arguments
            } catch [System.ArgumentException] {
                return @{ content = @(@{ type = 'text'; text = $_.Exception.Message }); isError = $true }
            } catch {
                return @{ content = @(@{ type = 'text'; text = "failed: $($_.Exception.Message)" }); isError = $true }
            }
            if ($result -is [string]) { $result = @(@{ type = 'text'; text = $result }) }
            return @{ content = @($result) }
        }
        'ping' { return @{} }
    }
    return $null
}

try {
    while ($null -ne ($line = [Console]::In.ReadLine())) {
        if ($line.Trim().Length -eq 0) { continue }
        $request = $line | ConvertFrom-Json
        if ($null -eq $request.PSObject.Properties['id']) { continue }  # a notification needs no reply
        $result = Get-Answer $request
        $reply = @{ jsonrpc = '2.0'; id = $request.id }
        if ($null -eq $result) { $reply.error = @{ code = -32601; message = 'method not found' } } else { $reply.result = $result }
        [Console]::Out.Write((ConvertTo-Json -InputObject $reply -Depth 20 -Compress) + "`n")
        [Console]::Out.Flush()
    }
} finally {
    # Let go of buttons still held when the server stops.
    foreach ($button in @($script:Held)) { try { [DesktopInput]::Mouse($ButtonFlags[$button][1], 0) } catch { } }
}
