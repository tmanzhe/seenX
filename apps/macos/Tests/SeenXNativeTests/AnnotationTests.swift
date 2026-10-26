import AppKit
import XCTest
@testable import SeenXNative

final class AnnotationTests: XCTestCase {
    private let first = TextBox(text: "remember", x: 0.1, y: 0.2, width: 0.2, height: 0.1)
    private let second = TextBox(text: "this", x: 0.4, y: 0.2, width: 0.1, height: 0.1)

    func testSubmitCommitsPendingBeforeItCanSave() {
        var state = AnnotationState(pending: [first, second])
        XCTAssertEqual(state.submit(), .committedHighlight)
        XCTAssertTrue(state.pending.isEmpty)
        XCTAssertEqual(state.highlights.first?.text, "remember this")
        XCTAssertEqual(state.submit(), .save)
    }

    func testDeleteClearsPendingBeforeExistingHighlights() {
        let saved = Highlight(boxes: [first])
        var state = AnnotationState(highlights: [saved], pending: [second], selected: saved.id)
        state.delete()
        XCTAssertEqual(state.highlights, [saved])
        XCTAssertTrue(state.pending.isEmpty)
        state.delete()
        XCTAssertTrue(state.highlights.isEmpty)
    }

    func testDeleteUsesSelectedHighlightThenMostRecent() {
        let a = Highlight(boxes: [first])
        let b = Highlight(boxes: [second])
        var state = AnnotationState(highlights: [a, b], selected: a.id)
        state.delete()
        XCTAssertEqual(state.highlights, [b])
        XCTAssertEqual(state.selected, b.id)
        state.selected = nil
        state.delete()
        XCTAssertTrue(state.highlights.isEmpty)
        state.delete()
        XCTAssertTrue(state.highlights.isEmpty)
    }

    func testOCRTokensKeepCodeAndPunctuation() {
        let text = "  C++ foo.bar(a) != nil\nuser@example.com  "
        XCTAssertEqual(NativeServices.tokenRanges(in: text).map { String(text[$0]) },
                       ["C++", "foo.bar(a)", "!=", "nil", "user@example.com"])
    }

    @MainActor
    func testNoteEditorAndHighlightsShareUndoHistory() {
        let session = AnnotationSession(url: URL(fileURLWithPath: "/unused"), image: NSImage(size: NSSize(width: 10, height: 10)))
        let textView = SharedUndoTextView()
        textView.sharedUndoManager = session.undoManager
        textView.allowsUndo = true
        XCTAssertTrue(textView.undoManager === session.undoManager)
        session.undoManager.groupsByEvent = false
        session.undoManager.beginUndoGrouping()
        textView.insertText("a note", replacementRange: NSRange(location: 0, length: 0))
        session.undoManager.endUndoGrouping()
        textView.breakUndoCoalescing()
        XCTAssertEqual(textView.string, "a note")
        session.undoManager.beginUndoGrouping()
        session.select([first])
        _ = session.submit()
        session.undoManager.endUndoGrouping()
        session.undoManager.undo()
        XCTAssertTrue(session.state.highlights.isEmpty)
        XCTAssertEqual(textView.string, "a note")
        session.undoManager.undo()
        XCTAssertEqual(textView.string, "")
        session.undoManager.redo()
        XCTAssertEqual(textView.string, "a note")
    }

    @MainActor
    func testHighlightUndoRedoRestoresPendingSelectionAndDeletion() {
        let session = AnnotationSession(url: URL(fileURLWithPath: "/unused"), image: NSImage(size: NSSize(width: 10, height: 10)))
        session.undoManager.groupsByEvent = false
        session.undoManager.beginUndoGrouping()
        session.select([first])
        session.undoManager.endUndoGrouping()
        session.undoManager.beginUndoGrouping()
        XCTAssertEqual(session.submit(), .committedHighlight)
        session.undoManager.endUndoGrouping()
        session.undoManager.undo()
        XCTAssertEqual(session.state.pending, [first])
        XCTAssertTrue(session.state.highlights.isEmpty)
        session.undoManager.redo()
        XCTAssertEqual(session.state.highlights.count, 1)
        session.undoManager.beginUndoGrouping()
        session.deleteHighlight()
        session.undoManager.endUndoGrouping()
        XCTAssertTrue(session.state.highlights.isEmpty)
        session.undoManager.undo()
        XCTAssertEqual(session.state.highlights.count, 1)
    }
}
