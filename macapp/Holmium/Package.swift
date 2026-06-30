// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "Holmium",
    platforms: [.macOS(.v14)],
    dependencies: [],
    targets: [
        .executableTarget(
            name: "Holmium",
            dependencies: [],
            resources: [.copy("Assets")]
        ),
    ]
)
