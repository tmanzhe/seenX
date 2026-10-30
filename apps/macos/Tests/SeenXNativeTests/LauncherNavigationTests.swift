import XCTest
@testable import SeenXNative

final class LauncherNavigationTests: XCTestCase {
    private let capture = SavedCapture(id: UUID(), createdAt: Date(), imageName: "fixture.png", note: "A useful memory", text: "invoice", highlights: [])

    @MainActor
    func testEscapeReturnsFromPreviewWithoutLosingSearchContext() {
        let navigation = LauncherNavigation()
        navigation.query = "invoice"
        navigation.selectedIndex = 2
        navigation.open(capture)
        XCTAssertEqual(navigation.screen, .detail(capture))
        XCTAssertTrue(navigation.handleEscape())
        XCTAssertEqual(navigation.screen, .search)
        XCTAssertEqual(navigation.query, "invoice")
        XCTAssertEqual(navigation.selectedIndex, 2)
        XCTAssertTrue(navigation.handleEscape())
        XCTAssertEqual(navigation.query, "")
        XCTAssertFalse(navigation.handleEscape())
    }

    @MainActor
    func testCatalogPreviewReturnsToTheSelectedEvidence() {
        let navigation = LauncherNavigation()
        navigation.query = "saved region"
        navigation.selectedIndex = 3
        navigation.openCatalogHit(id: "revision:note:annotation")
        XCTAssertEqual(navigation.screen, .catalogDetail("revision:note:annotation"))
        XCTAssertTrue(navigation.handleEscape())
        XCTAssertEqual(navigation.screen, .search)
        XCTAssertEqual(navigation.query, "saved region")
        XCTAssertEqual(navigation.selectedIndex, 3)
    }

    @MainActor
    func testLibraryPreviewHasItsOwnBackStack() {
        let navigation = LauncherNavigation()
        navigation.query = "original search"
        navigation.showLibrary()
        XCTAssertEqual(navigation.query, "")
        navigation.query = "saved note"
        navigation.open(capture)
        navigation.back()
        XCTAssertEqual(navigation.screen, .library)
        XCTAssertEqual(navigation.query, "saved note")
        navigation.back()
        XCTAssertEqual(navigation.screen, .search)
        XCTAssertEqual(navigation.query, "original search")
    }

    @MainActor
    func testEscapeClosesActionsBeforeChangingTheSearch() {
        let navigation = LauncherNavigation()
        navigation.query = "invoice"
        navigation.actionsPresented = true
        XCTAssertTrue(navigation.handleEscape())
        XCTAssertFalse(navigation.actionsPresented)
        XCTAssertEqual(navigation.query, "invoice")
        XCTAssertTrue(navigation.handleEscape())
        XCTAssertEqual(navigation.query, "")
    }

    @MainActor
    func testNewSummonResetsStalePreviewAndQuery() {
        let navigation = LauncherNavigation()
        navigation.showLibrary()
        navigation.query = "old search"
        navigation.open(capture)
        navigation.resetForSummon()
        XCTAssertEqual(navigation.screen, .search)
        XCTAssertEqual(navigation.query, "")
        XCTAssertEqual(navigation.selectedIndex, 0)
        XCTAssertFalse(navigation.handleEscape())
    }
}
