-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Máy chủ: localhost
-- Thời gian đã tạo: Th10 22, 2025 lúc 11:36 AM
-- Phiên bản máy phục vụ: 10.4.28-MariaDB
-- Phiên bản PHP: 8.2.4

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Cơ sở dữ liệu: `metro_facecheck`
--

-- --------------------------------------------------------

--
-- Cấu trúc bảng cho bảng `checkins`
--

CREATE TABLE `checkins` (
  `id` int(11) NOT NULL,
  `ticket_id` int(11) DEFAULT NULL,
  `user_id` int(11) DEFAULT NULL,
  `station` varchar(100) DEFAULT NULL,
  `checkin_time` datetime DEFAULT NULL,
  `success` tinyint(1) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Cấu trúc bảng cho bảng `face_data`
--

CREATE TABLE `face_data` (
  `id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `face_encoding` longblob DEFAULT NULL,
  `photo_path` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Cấu trúc bảng cho bảng `stations`
--

CREATE TABLE `stations` (
  `station_id` int(11) NOT NULL,
  `station_name` varchar(100) NOT NULL,
  `line` varchar(50) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Đang đổ dữ liệu cho bảng `stations`
--

INSERT INTO `stations` (`station_id`, `station_name`, `line`, `created_at`) VALUES
(0, 'Ga Bến Thành', NULL, '2025-11-03 22:48:39'),
(0, 'Ga Nhà hát Thành phố', NULL, '2025-11-03 22:48:39'),
(0, 'Ga Ba Son', NULL, '2025-11-03 22:48:39'),
(0, 'Ga Công viên Văn Thánh', NULL, '2025-11-03 22:48:39'),
(0, 'Ga Tân Cảng', NULL, '2025-11-03 22:48:39'),
(0, 'Ga Thảo Điền', NULL, '2025-11-03 22:48:39'),
(0, 'Ga An Phú', NULL, '2025-11-03 22:48:39'),
(0, 'Ga Rạch Chiếc', NULL, '2025-11-03 22:48:39'),
(0, 'Ga Phước Long', NULL, '2025-11-03 22:48:39'),
(0, 'Ga Bình Thái', NULL, '2025-11-03 22:48:40'),
(0, 'Ga Thủ Đức', NULL, '2025-11-03 22:48:40'),
(0, 'Ga Khu Công nghệ cao', NULL, '2025-11-03 22:48:40'),
(0, 'Ga Đại học Quốc gia', NULL, '2025-11-03 22:48:40'),
(0, 'Ga Bến xe Suối Tiên', NULL, '2025-11-03 22:48:40');

-- --------------------------------------------------------

--
-- Cấu trúc bảng cho bảng `tickets`
--

CREATE TABLE `tickets` (
  `id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `ticket_type` enum('monthly','single') NOT NULL,
  `purchase_time` datetime NOT NULL,
  `valid_from` date DEFAULT NULL,
  `valid_to` date DEFAULT NULL,
  `single_from_station` varchar(100) DEFAULT NULL,
  `single_to_station` varchar(100) DEFAULT NULL,
  `used` tinyint(1) DEFAULT 0,
  `trip_code` varchar(100) DEFAULT NULL,
  `from_station_id` int(11) DEFAULT NULL,
  `to_station_id` int(11) DEFAULT NULL,
  `from_station_name` varchar(255) DEFAULT NULL,
  `to_station_name` varchar(255) DEFAULT NULL,
  `status` varchar(20) DEFAULT NULL,
  `purchase_price` int(11) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Cấu trúc bảng cho bảng `users`
--

CREATE TABLE `users` (
  `id` int(11) NOT NULL,
  `username` varchar(100) NOT NULL,
  `phone` varchar(20) DEFAULT NULL,
  `email` varchar(150) DEFAULT NULL,
  `password` varchar(255) NOT NULL,
  `role` enum('user','admin') DEFAULT 'user',
  `face_registered` tinyint(1) DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Đang đổ dữ liệu cho bảng `users`
--

INSERT INTO `users` (`id`, `username`, `phone`, `email`, `password`, `role`, `face_registered`) VALUES
(1, 'admin', '0123456789', 'admin@example.com', 'admin123', 'admin', 0);

--
-- Chỉ mục cho các bảng đã đổ
--

--
-- Chỉ mục cho bảng `checkins`
--
ALTER TABLE `checkins`
  ADD PRIMARY KEY (`id`),
  ADD KEY `ticket_id` (`ticket_id`),
  ADD KEY `user_id` (`user_id`);

--
-- Chỉ mục cho bảng `face_data`
--
ALTER TABLE `face_data`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `user_id` (`user_id`);

--
-- Chỉ mục cho bảng `tickets`
--
ALTER TABLE `tickets`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `trip_code` (`trip_code`),
  ADD KEY `user_id` (`user_id`);

--
-- Chỉ mục cho bảng `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `username` (`username`);

--
-- AUTO_INCREMENT cho các bảng đã đổ
--

--
-- AUTO_INCREMENT cho bảng `checkins`
--
ALTER TABLE `checkins`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT cho bảng `face_data`
--
ALTER TABLE `face_data`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=3;

--
-- AUTO_INCREMENT cho bảng `tickets`
--
ALTER TABLE `tickets`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=7;

--
-- AUTO_INCREMENT cho bảng `users`
--
ALTER TABLE `users`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=8;

--
-- Các ràng buộc cho các bảng đã đổ
--

--
-- Các ràng buộc cho bảng `checkins`
--
ALTER TABLE `checkins`
  ADD CONSTRAINT `checkins_ibfk_1` FOREIGN KEY (`ticket_id`) REFERENCES `tickets` (`id`) ON DELETE SET NULL,
  ADD CONSTRAINT `checkins_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE;

--
-- Các ràng buộc cho bảng `face_data`
--
ALTER TABLE `face_data`
  ADD CONSTRAINT `fk_face_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE;

--
-- Các ràng buộc cho bảng `tickets`
--
ALTER TABLE `tickets`
  ADD CONSTRAINT `tickets_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
