import Foundation

enum OverlayDirection: UInt32, CaseIterable {
    case left = 10, right, down, up

    var keyCode: UInt32 {
        switch self {
        case .left: return 123
        case .right: return 124
        case .down: return 125
        case .up: return 126
        }
    }

    var symbol: String {
        switch self {
        case .left: return "←"
        case .right: return "→"
        case .down: return "↓"
        case .up: return "↑"
        }
    }

    /// Keep the entire overlay reachable, including displays with negative origins.
    func moving(_ frame: CGRect, inside display: CGRect, step: CGFloat = 24) -> CGRect {
        var result = frame
        switch self {
        case .left: result.origin.x -= step
        case .right: result.origin.x += step
        case .down: result.origin.y -= step
        case .up: result.origin.y += step
        }
        result.origin.x = min(max(result.minX, display.minX), max(display.minX, display.maxX - result.width))
        result.origin.y = min(max(result.minY, display.minY), max(display.minY, display.maxY - result.height))
        return result
    }
}
