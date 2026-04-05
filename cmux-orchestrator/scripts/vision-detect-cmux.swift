#!/usr/bin/env swift
// vision-detect-cmux.swift — Apple Vision으로 화면에서 /cmux 패턴 감지
// 전체 화면 스크린샷 → OCR → /cmux 입력 패턴 탐색
// 프롬프트 입력창까지 캡처 가능 (read-screen으로 못 잡는 것도 감지)
//
// 사용법: swift vision-detect-cmux.swift
// 출력: JSON {"found": bool, "surfaces": [{"text": "❯ /cmux", "bounds": {...}}]}

import Vision
import AppKit
import Foundation

// 전체 화면 스크린샷
let tmpPath = "/tmp/cmux-vision-fullscreen.png"
let process = Process()
process.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
process.arguments = ["-x", "-C", tmpPath]  // -x: 소리 없이, -C: 커서 포함
try process.run()
process.waitUntilExit()

guard FileManager.default.fileExists(atPath: tmpPath),
      let image = NSImage(contentsOfFile: tmpPath),
      let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    print(#"{"found": false, "error": "screenshot failed"}"#)
    exit(1)
}

// Vision OCR
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.recognitionLanguages = ["en", "ko"]
request.usesLanguageCorrection = false

let handler = VNImageRequestHandler(cgImage: cgImage)
try handler.perform([request])

var found = false
var matches: [[String: Any]] = []

for observation in request.results ?? [] {
    guard let candidate = observation.topCandidates(1).first else { continue }
    let text = candidate.string

    // /cmux 패턴 감지 (프롬프트 입력창)
    if text.contains("/cmux") && !text.contains("/cmux-") && !text.contains("/cmux —") {
        found = true
        let box = observation.boundingBox
        matches.append([
            "text": text,
            "confidence": candidate.confidence,
            "bounds": [
                "x": box.origin.x,
                "y": box.origin.y,
                "width": box.width,
                "height": box.height
            ]
        ])
    }
}

// JSON 출력
let result: [String: Any] = ["found": found, "matches": matches]
if let data = try? JSONSerialization.data(withJSONObject: result),
   let json = String(data: data, encoding: .utf8) {
    print(json)
}

// 임시 파일 정리
try? FileManager.default.removeItem(atPath: tmpPath)
