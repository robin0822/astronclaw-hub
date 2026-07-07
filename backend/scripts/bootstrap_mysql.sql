CREATE DATABASE IF NOT EXISTS `astronclaw`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'astronclaw'@'localhost' IDENTIFIED BY 'astronclaw';
CREATE USER IF NOT EXISTS 'astronclaw'@'%' IDENTIFIED BY 'astronclaw';

GRANT ALL PRIVILEGES ON `astronclaw`.* TO 'astronclaw'@'localhost';
GRANT ALL PRIVILEGES ON `astronclaw`.* TO 'astronclaw'@'%';
FLUSH PRIVILEGES;
