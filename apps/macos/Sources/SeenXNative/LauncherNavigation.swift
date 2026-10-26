import Combine
import Foundation

enum LauncherScreen: Equatable {
    case search
    case library
    case detail(SavedCapture)
}

/// A launcher has one window and a back stack; previews never become modal sheets.
@MainActor
final class LauncherNavigation: ObservableObject {
    @Published private(set) var screen: LauncherScreen = .search
    @Published var query = ""
    @Published var selectedIndex = 0
    @Published var actionsPresented = false
    private var history: [(screen: LauncherScreen, query: String, selection: Int)] = []

    func showLibrary() {
        guard screen != .library else { return }
        actionsPresented = false
        push()
        query = ""
        selectedIndex = 0
        screen = .library
    }

    func open(_ capture: SavedCapture) {
        actionsPresented = false
        push()
        screen = .detail(capture)
    }

    func back() {
        actionsPresented = false
        guard let previous = history.popLast() else { resetForSummon(); return }
        query = previous.query
        selectedIndex = previous.selection
        screen = previous.screen
    }

    /// Escape unwinds the current screen, then the query, before dismissing.
    @discardableResult
    func handleEscape() -> Bool {
        if actionsPresented { actionsPresented = false; return true }
        if screen != .search { back(); return true }
        if !query.isEmpty { query = ""; selectedIndex = 0; return true }
        return false
    }

    func resetForSummon() {
        actionsPresented = false
        history.removeAll()
        query = ""
        selectedIndex = 0
        screen = .search
    }

    private func push() { history.append((screen, query, selectedIndex)) }
}
