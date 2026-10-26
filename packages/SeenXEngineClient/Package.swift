// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "SeenXEngineClient",
    platforms: [.macOS(.v14)],
    products: [.library(name: "SeenXEngineClient", targets: ["SeenXEngineClient"])],
    targets: [
        .target(name: "SeenXEngineClient"),
        .testTarget(name: "SeenXEngineClientTests", dependencies: ["SeenXEngineClient"])
    ]
)
