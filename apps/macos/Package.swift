// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "SeenXNative",
    platforms: [.macOS(.v14)],
    products: [.executable(name: "SeenXNative", targets: ["SeenXNative"])],
    dependencies: [.package(path: "../../packages/SeenXEngineClient")],
    targets: [
        .executableTarget(name: "SeenXNative", dependencies: ["SeenXEngineClient"]),
        .testTarget(name: "SeenXNativeTests", dependencies: ["SeenXNative"])
    ]
)
