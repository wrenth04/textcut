# TextCut ✂️

TextCut 是一個輕量級的螢幕文字擷取工具。它允許使用者透過快捷鍵快速選取螢幕上的任意區域，自動辨認其中的文字，並直接將結果複製到剪貼簿，讓你可以像複製一般文字一樣使用 `Ctrl + V` 貼上。

## ✨ 功能特點

- **全域快捷鍵**: 無需切換視窗，按下快捷鍵立即啟動。
- **直覺化選取**: 提供半透明覆蓋層，透過滑鼠拖曳輕鬆定義擷取範圍。
- **內建 OCR**: 在 Windows 上使用系統內建 OCR，並對中文結果做後處理，減少字間多餘空白。
- **無縫貼上**: 辨認結果直接進入系統剪貼簿。
- **極輕量**: 依賴極少，啟動快速。

## 🚀 快速開始 (Windows)

### 1. 環境準備
確保你的電腦已安裝 **Python 3.11+**。

### 2. 安裝依賴
在專案根目錄執行以下指令安裝必要的套件：
```bash
pip install -r requirements.txt
```

### 3. 啟動工具
執行主程式：
```bash
python src/main.py
```

## ⌨️ 使用指南

1. **觸發擷取**: 按下 `Alt + C`。
2. **選取文字**: 螢幕會變暗，請使用滑鼠 **左鍵拖曳** 選取包含文字的區域。
3. **完成辨認**: 放開滑鼠後，程式將自動執行 OCR 辨認。
4. **貼上文字**: 在任何文字編輯器中按下 `Ctrl + V` 即可貼上辨認出的文字。
5. **取消操作**: 在選取模式下按下 `Esc` 鍵可取消本次擷取。

## 🛠️ 技術棧

- **語言**: Python
- **OCR 引擎**: Windows WinRT OCR (`winrt.windows.media.ocr`)
- **截圖模組**: Windows GDI / `ctypes`
- **UI 介面**: `tkinter` (用於選取覆蓋層與通知)
- **影像處理**: Windows API

## 📦 打包為執行檔 (.exe)

如果你希望將其打包成單一執行檔方便分發，可以使用 PyInstaller：

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name textcut src/main.py
```
打包後的檔案將位於 `dist/textcut.exe`。

## 🗺️ 未來計畫

- [ ] **macOS 支援**: 整合 Apple Vision Framework 實現原生 OCR。
- [ ] **Linux 支援**: 整合 Tesseract OCR 提供跨平台能力。
- [ ] **自定義快捷鍵**: 增加設定介面允許使用者修改快捷鍵。
- [ ] **多語言支援**: 自動偵測或手動切換辨認語言。

---
*TextCut - 讓螢幕上的文字隨手可得。*
