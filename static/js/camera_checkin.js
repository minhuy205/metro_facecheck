// 1. LẤY CÁC ELEMENT (từ tệp 1 của bạn)
const video = document.getElementById("video")
const startBtn = document.getElementById("start")
const statusDiv = document.getElementById("status")
const resultDiv = document.getElementById("result")
const stationSelect = document.getElementById("station")
const videoContainer = document.getElementById("video-container")


// 2. THÊM LOGIC COOLDOWN
// ✨ SỬA Ở ĐÂY: Giảm thời gian chờ xuống 500ms (nửa giây) cho mượt hơn
const CHECK_INTERVAL = 500
const COOLDOWN = 60000 // 60 giây cooldown (giữ nguyên)
const recentCheckins = new Map()


let isCheckinActive = false


// 3. HÀM START
startBtn.addEventListener("click", async () => {
  const station = stationSelect.value // Đây là TÊN GA (ví dụ: "Ga Bến Thành")
  if (!station) {
    statusDiv.textContent = "Vui lòng chọn ga trước"
    statusDiv.style.color = "#ff3333"
    return
  }


  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true })
    video.srcObject = stream
    videoContainer.style.display = "block"
    isCheckinActive = true
    startBtn.disabled = true
    startBtn.textContent = "Đang Kiểm Soát..."
    statusDiv.textContent = "Camera hoạt động - Đặt khuôn mặt vào hộp"
    statusDiv.style.color = "#0066cc"


    // Bắt đầu vòng lặp
    performCheck(station)
  } catch (err) {
    statusDiv.textContent =
      "Truy cập camera bị từ chối. Vui lòng cho phép truy cập camera."
    statusDiv.style.color = "#ff3333"
    console.error("Lỗi camera:", err)
  }
})


// 4. HÀM CHECK-IN
async function performCheck(station) {
  if (!isCheckinActive) return


  // Đặt trạng thái "Đang kiểm tra"
  statusDiv.textContent = "🔍 Đang kiểm tra..."
  statusDiv.style.color = "#0066cc"
  resultDiv.style.display = "none"


  const canvas = document.createElement("canvas")
  const ctx = canvas.getContext("2d")


  try {
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    ctx.drawImage(video, 0, 0)


    const imageData = canvas.toDataURL("image/jpeg")


    const response = await fetch("/api/checkin", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        image_b64: imageData,
        // ✨ SỬA Ở ĐÂY: Đổi 'station_id' thành 'station' để khớp với app.py
        station: station,
      }),
    })


    if (!response.ok) {
         throw new Error(`HTTP error! status: ${response.status}`);
    }


    const result = await response.json()


    // --- LOGIC GỘP BẮT ĐẦU TỪ ĐÂY ---
    if (result.success) {
      // Server trả về thành công
      const userId = result.user_id // Server của bạn PHẢI trả về user_id


      if (!userId) {
        // Fallback nếu server không trả về user_id
        console.warn("Server không trả về user_id, bỏ qua cooldown.")
        resultDiv.textContent = `✓ ${result.message}`
        resultDiv.className = "result-message success"
        resultDiv.style.display = "block"
        statusDiv.textContent = "Vé hợp lệ - Vui lòng vào"
        statusDiv.style.color = "#00cc66"
      } else {
        // Có user_id, ÁP DỤNG LOGIC COOLDOWN
        const lastCheck = recentCheckins.get(userId) || 0
        const now = Date.now()


        if (now - lastCheck < COOLDOWN) {
          // Vẫn đang trong thời gian cooldown 60s
          resultDiv.textContent = `✓ ${userId} đã check-in`
          resultDiv.className = "result-message warning" // (Màu vàng)
          resultDiv.style.display = "block"
          statusDiv.textContent = "Đã check-in gần đây, vui lòng chờ."
          statusDiv.style.color = "#ffeb3b"
        } else {
          // Hết cooldown, cho phép check-in
          recentCheckins.set(userId, now) // Đặt lại thời gian
          resultDiv.textContent = `✓ ${
            result.message || `User ${userId} - Vé hợp lệ`
          }`
          resultDiv.className = "result-message success"
          resultDiv.style.display = "block"
          statusDiv.textContent = "Vé hợp lệ - Vui lòng vào"
          statusDiv.style.color = "#00cc66"
        }
      }
    } else {
      // Check-in thất bại
      resultDiv.textContent = `✗ ${result.message || "Kiểm soát thất bại"}`
      resultDiv.className = "result-message error"
      resultDiv.style.display = "block"
      statusDiv.textContent = "Vé không hợp lệ hoặc khuôn mặt không được nhận diện"
      statusDiv.style.color = "#ff3333"
    }
    // --- LOGIC GỘP KẾT THÚC ---
  } catch (err) {
    // Lỗi mạng
    console.error("Lỗi kiểm soát:", err)
    statusDiv.textContent = "⚠️ Lỗi kết nối server"
    statusDiv.style.color = "#ff3333" // (Màu đỏ cho lỗi)
  } finally {
    // Luôn gọi lại vòng lặp (bây giờ là sau 0.5 giây)
    setTimeout(() => performCheck(station), CHECK_INTERVAL)
  }
}


