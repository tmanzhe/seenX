// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "SeenXNative",
    platforms: [.macOS(.v14)],
    products: [.executable(name: "SeenXNative", targets: ["SeenXNative"])],
    targets: [
        .executableTarget(name: "SeenXNative"),
        .testTarget(name: "SeenXNativeTests", dependencies: ["SeenXNative"])
    ]
)
