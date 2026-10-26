import XCTest
@testable import SeenXNative

final class OverlayMovementTests: XCTestCase {
    func testMovingKeepsTheOverlaySizeAndMovesInScreenCoordinates() {
        let display = CGRect(x: 0, y: 40, width: 1440, height: 860)
        let frame = CGRect(x: 400, y: 300, width: 640, height: 312)
        let moved = OverlayDirection.up.moving(frame, inside: display)
        XCTAssertEqual(moved.origin, CGPoint(x: 400, y: 324))
        XCTAssertEqual(moved.size, frame.size)
        XCTAssertEqual(OverlayDirection.down.moving(moved, inside: display), frame)
        XCTAssertEqual(OverlayDirection.right.moving(OverlayDirection.left.moving(frame, inside: display), inside: display), frame)
    }

    func testRepeatedMovementStopsAtEveryVisibleEdge() {
        let display = CGRect(x: 0, y: 40, width: 1440, height: 860)
        let center = CGRect(x: 400, y: 300, width: 640, height: 312)
        for direction in OverlayDirection.allCases {
            let edge = (0..<200).reduce(center) { frame, _ in direction.moving(frame, inside: display) }
            XCTAssertTrue(display.contains(edge))
            XCTAssertEqual(direction.moving(edge, inside: display), edge)
        }
    }

    func testMovementHandlesDisplaysLeftOfTheMainScreen() {
        let display = CGRect(x: -1920, y: -200, width: 1920, height: 1080)
        let frame = CGRect(x: -1916, y: -194, width: 640, height: 312)
        let left = OverlayDirection.left.moving(frame, inside: display)
        let bottom = OverlayDirection.down.moving(left, inside: display)
        XCTAssertEqual(bottom.origin, display.origin)
        XCTAssertEqual(bottom.size, frame.size)
    }

    func testOversizedOverlayKeepsItsOriginReachable() {
        let display = CGRect(x: -800, y: 40, width: 800, height: 500)
        let frame = CGRect(x: -400, y: 100, width: 1000, height: 740)
        let moved = OverlayDirection.right.moving(frame, inside: display)
        XCTAssertEqual(moved.origin, display.origin)
        XCTAssertEqual(moved.size, frame.size)
    }
}
