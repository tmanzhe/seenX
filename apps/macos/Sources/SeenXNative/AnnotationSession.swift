import AppKit
import Combine

@MainActor
final class AnnotationSession: ObservableObject, Identifiable {
    let id = UUID()
    let imageURL: URL
    let image: NSImage
    @Published var note = ""
    @Published var boxes: [TextBox] = []
    @Published var recognizing = true
    @Published var error: String?
    @Published private(set) var state = AnnotationState()
    let undoManager = UndoManager()

    init(url: URL, image: NSImage) { imageURL = url; self.image = image }

    private func restore(_ value: AnnotationState) {
        let previous = state
        undoManager.registerUndo(withTarget: self) { $0.restore(previous) }
        state = value
    }

    func select(_ boxes: [TextBox]) {
        var next = state
        next.pending = boxes
        next.selected = nil
        if next != state { restore(next); undoManager.setActionName("Text selection") }
    }

    func selectHighlight(_ id: UUID) {
        var next = state
        next.selected = id
        next.pending = []
        restore(next)
    }

    func submit() -> SubmitAction {
        var next = state
        let action = next.submit()
        if next != state { restore(next); undoManager.setActionName("Highlight") }
        return action
    }

    func deleteHighlight() {
        var next = state
        next.delete()
        if next != state { restore(next); undoManager.setActionName("Delete highlight") }
    }

    func cancelPending() -> Bool {
        guard !state.pending.isEmpty else { return false }
        select([])
        return true
    }
}
