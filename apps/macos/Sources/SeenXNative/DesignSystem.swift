import AppKit
import SwiftUI

private struct SeenXForceOpaqueKey: EnvironmentKey {
    static let defaultValue = false
}

extension EnvironmentValues {
    /// Preview/QA override exercises the same fallback as Reduce Transparency.
    var seenXForceOpaque: Bool {
        get { self[SeenXForceOpaqueKey.self] }
        set { self[SeenXForceOpaqueKey.self] = newValue }
    }
}

/// Semantic colors from the seenX design proposal. Screenshots retain their own colors.
struct SeenXTheme {
    let scheme: ColorScheme
    private func color(_ light: UInt32, _ dark: UInt32) -> Color { Color(nsColor: nsColor(light, dark)) }
    private func nsColor(_ light: UInt32, _ dark: UInt32) -> NSColor {
        let value = scheme == .dark ? dark : light
        return NSColor(srgbRed: Double((value >> 16) & 255) / 255,
                       green: Double((value >> 8) & 255) / 255,
                       blue: Double(value & 255) / 255, alpha: 1)
    }
    var background: Color { color(0xF4F8FF, 0x0E192C) }
    var surface: Color { color(0xEAF1FC, 0x172840) }
    var panel: Color { color(0xFBFDFF, 0x122139) }
    var primary: Color { color(0x182B49, 0xE5EFFF) }
    var secondary: Color { color(0x5B6F8B, 0xA0B4D1) }
    var border: Color { color(0xD7E3F3, 0x2C4160) }
    var brand: Color { color(0x4888DF, 0x8DBBFF) }
    var accent: Color { color(0x2867BC, 0xA3C9FF) }
    var selection: Color { color(0xD2E5FF, 0x24466E) }
    var nativePrimary: NSColor { nsColor(0x182B49, 0xE5EFFF) }
    var nativeSecondary: NSColor { nsColor(0x5B6F8B, 0xA0B4D1) }
}

private struct DesktopGlass: NSViewRepresentable {
    let scheme: ColorScheme
    let radius: CGFloat
    func makeNSView(context: Context) -> NSView {
        if #available(macOS 26.0, *) {
            let view = NSGlassEffectView()
            view.style = .clear
            view.cornerRadius = radius
            return view
        }
        let view = NSVisualEffectView()
        view.material = .popover
        view.blendingMode = .behindWindow
        view.state = .active
        view.alphaValue = 0.65
        return view
    }
    func updateNSView(_ view: NSView, context: Context) {
        view.appearance = NSAppearance(named: scheme == .dark ? .darkAqua : .aqua)
        if #available(macOS 26.0, *), let glass = view as? NSGlassEffectView {
            glass.cornerRadius = radius
            glass.tintColor = scheme == .dark
                ? NSColor(srgbRed: 0.14, green: 0.22, blue: 0.34, alpha: 0.04)
                : NSColor(srgbRed: 0.97, green: 0.99, blue: 1, alpha: 0.035)
        }
    }
}

private struct GlassPanel: ViewModifier {
    @Environment(\.colorScheme) private var scheme
    @Environment(\.accessibilityReduceTransparency) private var reduceTransparency
    @Environment(\.seenXForceOpaque) private var forceOpaque
    let radius: CGFloat
    let opacity: Double
    func body(content: Content) -> some View {
        let theme = SeenXTheme(scheme: scheme)
        content
            .background {
                if reduceTransparency || forceOpaque { theme.panel }
                else {
                    DesktopGlass(scheme: scheme, radius: radius)
                        .overlay {
                            LinearGradient(colors: scheme == .dark
                                ? [theme.panel.opacity(0.035), theme.panel.opacity(0.015)]
                                : [Color.white.opacity(0.06), Color.white.opacity(0.015)],
                                           startPoint: .topLeading, endPoint: .bottomTrailing)
                        }
                        .overlay(theme.brand.opacity(0.008))
                        .opacity(opacity)
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: radius, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .strokeBorder(LinearGradient(colors: reduceTransparency || forceOpaque
                        ? [theme.border, theme.border]
                        : [Color.white.opacity(scheme == .dark ? 0.24 : 0.90), theme.brand.opacity(0.26)],
                                                 startPoint: .topLeading, endPoint: .bottomTrailing), lineWidth: 1)
            }
            .overlay {
                if !reduceTransparency && !forceOpaque {
                    RoundedRectangle(cornerRadius: max(0, radius - 1), style: .continuous)
                        .inset(by: 1).strokeBorder(Color.white.opacity(scheme == .dark ? 0.06 : 0.22), lineWidth: 0.5)
                }
            }
    }
}

extension View {
    func seenXGlass(radius: CGFloat = 20, opacity: Double = 1) -> some View {
        modifier(GlassPanel(radius: radius, opacity: opacity))
    }
}

struct ShortcutBadge: View {
    let text: String
    @Environment(\.colorScheme) private var scheme
    var body: some View {
        let theme = SeenXTheme(scheme: scheme)
        Text(text).font(.system(size: 11, weight: .medium, design: .monospaced))
            .foregroundStyle(theme.secondary).padding(.horizontal, 6).padding(.vertical, 4)
            .background(theme.surface.opacity(0.20), in: RoundedRectangle(cornerRadius: 6))
            .overlay(RoundedRectangle(cornerRadius: 6).stroke(theme.border.opacity(0.4), lineWidth: 1))
    }
}

struct SeenXActionStyle: ButtonStyle {
    var prominent = false
    @Environment(\.colorScheme) private var scheme
    func makeBody(configuration: Configuration) -> some View {
        let theme = SeenXTheme(scheme: scheme)
        configuration.label.font(.system(size: 13, weight: .medium))
            .foregroundStyle(prominent ? (scheme == .dark ? theme.background : Color.white) : theme.primary)
            .padding(.horizontal, 14).padding(.vertical, 9)
            .background((prominent ? theme.accent : theme.surface).opacity(configuration.isPressed ? 0.72 : 1),
                        in: RoundedRectangle(cornerRadius: 10))
            .overlay(RoundedRectangle(cornerRadius: 10).stroke(prominent ? .clear : theme.border, lineWidth: 1))
    }
}
