import AppKit
import SeenXEngineClient
import SwiftUI

struct CatalogRegionDraft {
    var annotationID: String?
    var note = ""
    var rectangle: CGRect?
    var geometryChanged = false

    init() {}

    init(annotation: Annotation) {
        annotationID = annotation.id
        note = annotation.note
        if annotation.target.kind == "region" {
            rectangle = CGRect(x: annotation.target.x, y: annotation.target.y,
                               width: annotation.target.width, height: annotation.target.height)
        }
    }

    var coordinates: [Double]? {
        rectangle.map { [Double($0.minX), Double($0.minY), Double($0.width), Double($0.height)] }
    }

    /// The gesture belongs to the fitted image, so letterboxing is outside its
    /// coordinate space. Reverse drags and drags beyond an edge are supported.
    static func rectangle(from start: CGPoint, to end: CGPoint, imageSize: CGSize) -> CGRect? {
        guard imageSize.width > 0, imageSize.height > 0,
              start.x.isFinite, start.y.isFinite, end.x.isFinite, end.y.isFinite,
              start.x >= 0, start.y >= 0, start.x <= imageSize.width, start.y <= imageSize.height else { return nil }
        let x = min(max(end.x, 0), imageSize.width)
        let y = min(max(end.y, 0), imageSize.height)
        guard abs(x - start.x) >= 3, abs(y - start.y) >= 3 else { return nil }
        let left = min(start.x, x) / imageSize.width
        let top = min(start.y, y) / imageSize.height
        let right = max(start.x, x) / imageSize.width
        let bottom = max(start.y, y) / imageSize.height
        return CGRect(x: left, y: top, width: right - left, height: bottom - top)
    }
}

struct CatalogRegionCanvas: View {
    @ObservedObject var model: EngineBrowserModel
    let image: NSImage
    let annotations: [Annotation]
    @State private var dragRectangle: CGRect?

    var body: some View {
        GeometryReader { geometry in
            let scale = min(geometry.size.width / image.size.width, geometry.size.height / image.size.height)
            let size = CGSize(width: image.size.width * scale, height: image.size.height * scale)
            Image(nsImage: image).resizable().frame(width: size.width, height: size.height)
                .overlay(alignment: .topLeading) {
                    ZStack(alignment: .topLeading) {
                        ForEach(annotations) { annotation in
                            let target = annotation.target
                            let selected = model.regionDraft?.annotationID == annotation.id
                            if target.kind == "point" {
                                Circle().fill(selected ? Color.accentColor : .orange).frame(width: 8, height: 8)
                                    .offset(x: target.x * size.width - 4, y: target.y * size.height - 4)
                            } else {
                                outline(CGRect(x: target.x, y: target.y, width: target.width, height: target.height),
                                        size: size, color: selected ? .accentColor : .orange)
                            }
                        }
                        if model.regionDraft == nil, let target = model.selected?.target, model.selected?.observationID != nil {
                            outline(CGRect(x: target.x, y: target.y, width: target.width, height: target.height), size: size, color: .orange)
                        }
                        if let rect = dragRectangle ?? (model.regionDraft?.geometryChanged == true ? model.regionDraft?.rectangle : nil) {
                            outline(rect, size: size, color: .accentColor)
                        }
                    }.allowsHitTesting(false)
                }
                .contentShape(Rectangle())
                .gesture(DragGesture(minimumDistance: 0)
                    .onChanged { value in
                        guard model.drawingRegion, !model.busy else { return }
                        dragRectangle = CatalogRegionDraft.rectangle(from: value.startLocation, to: value.location, imageSize: size)
                    }
                    .onEnded { value in
                        defer { dragRectangle = nil }
                        guard !model.busy else { return }
                        if model.drawingRegion {
                            if let rect = CatalogRegionDraft.rectangle(from: value.startLocation, to: value.location, imageSize: size) {
                                model.finishDrawing(rect)
                            }
                        } else if !model.hasRegionChanges, size.width > 0, size.height > 0 {
                            let point = CGPoint(x: value.location.x / size.width, y: value.location.y / size.height)
                            let hit = annotations.reversed().first { annotation in
                                let target = annotation.target
                                if target.kind == "point" {
                                    return abs(point.x - target.x) * size.width <= 8 && abs(point.y - target.y) * size.height <= 8
                                }
                                return point.x >= target.x && point.x <= target.x + target.width &&
                                    point.y >= target.y && point.y <= target.y + target.height
                            }
                            model.selectAnnotation(hit)
                        }
                    })
                .accessibilityLabel(model.drawingRegion ? "Drag a rectangle on the image" : "Saved image with regions; select a region below to edit")
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }.frame(minHeight: 160)
    }

    private func outline(_ rectangle: CGRect, size: CGSize, color: Color) -> some View {
        Rectangle().fill(color.opacity(0.12)).border(color, width: 2)
            .frame(width: rectangle.width * size.width, height: rectangle.height * size.height)
            .offset(x: rectangle.minX * size.width, y: rectangle.minY * size.height)
    }
}

struct CatalogRegionControls: View {
    @ObservedObject var model: EngineBrowserModel
    let annotations: [Annotation]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Saved regions (\(annotations.count))").font(.caption)
                Spacer()
                Button("New region", action: model.newRegion)
                    .disabled(!model.canEditRegions || model.hasRegionChanges)
            }
            ScrollView(.horizontal) {
                HStack {
                    ForEach(Array(annotations.enumerated()), id: \.element.id) { index, annotation in
                        Button("\(index + 1). \(annotation.note.isEmpty ? annotation.selectedText : annotation.note)") {
                            model.selectAnnotation(annotation)
                        }
                        .lineLimit(1).frame(maxWidth: 180)
                        .tint(model.regionDraft?.annotationID == annotation.id ? .accentColor : .secondary)
                        .disabled(model.hasRegionChanges)
                    }
                }
            }
            if model.regionDraft != nil {
                if model.canEditRegions {
                    if model.drawingRegion { Text("Drag on the image to draw the region.").font(.caption) }
                    TextField("Region note", text: Binding(get: { model.regionDraft?.note ?? "" },
                                                           set: { model.regionDraft?.note = $0 }), axis: .vertical)
                        .textFieldStyle(.roundedBorder).lineLimit(2...3)
                    HStack {
                        Button("Redraw") { model.drawingRegion = true }
                        Button("Save", action: model.saveRegion).disabled(!model.canSaveRegion)
                        Button("Cancel", action: model.cancelRegionDraft)
                        Button("Delete", role: .destructive, action: model.deleteRegion)
                            .disabled(model.selectedAnnotation == nil || model.hasRegionChanges || model.drawingRegion)
                    }
                } else if let annotation = model.selectedAnnotation {
                    Text(annotation.note).textSelection(.enabled)
                }
                if let annotation = model.selectedAnnotation, !annotation.selectedText.isEmpty {
                    Text(annotation.selectedText).font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
                }
                HStack {
                    Picker("Image", selection: $model.payloadImageMode) {
                        Text("Region crop").tag("crop")
                        Text("Full image").tag("full")
                    }.frame(maxWidth: 210)
                    Button("Copy for LLM") { model.copyForLLM() }
                        .disabled(!model.canCopyPayload || model.selectedAnnotation == nil || model.hasRegionChanges || model.drawingRegion)
                }
                if let status = model.copyStatus { Text(status).font(.caption).foregroundStyle(.secondary) }
            } else {
                Text("Select a saved region, or choose New region and draw on the image.")
                    .font(.caption).foregroundStyle(.secondary)
            }
        }.disabled(model.busy || !model.connected || model.showingCrop)
    }
}
