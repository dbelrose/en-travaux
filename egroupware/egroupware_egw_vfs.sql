-- MySQL dump 10.13  Distrib 8.0.31, for Win64 (x86_64)
--
-- Host: dbpnf.srv.gov.pf    Database: egroupware
-- ------------------------------------------------------
-- Server version	5.5.43-0+deb7u1

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `egw_vfs`
--

DROP TABLE IF EXISTS `egw_vfs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `egw_vfs` (
  `vfs_file_id` int(11) NOT NULL AUTO_INCREMENT,
  `vfs_owner_id` int(11) NOT NULL DEFAULT '0',
  `vfs_createdby_id` int(11) DEFAULT NULL,
  `vfs_modifiedby_id` int(11) DEFAULT NULL,
  `vfs_created` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `vfs_modified` datetime DEFAULT NULL,
  `vfs_size` int(11) DEFAULT NULL,
  `vfs_mime_type` varchar(64) DEFAULT NULL,
  `vfs_deleteable` char(1) DEFAULT 'Y',
  `vfs_comment` varchar(255) DEFAULT NULL,
  `vfs_app` varchar(25) DEFAULT NULL,
  `vfs_directory` varchar(233) DEFAULT NULL,
  `vfs_name` varchar(100) NOT NULL DEFAULT '',
  `vfs_link_directory` varchar(255) DEFAULT NULL,
  `vfs_link_name` varchar(128) DEFAULT NULL,
  `vfs_version` varchar(30) NOT NULL DEFAULT '0.0.0.0',
  `vfs_content` longblob,
  PRIMARY KEY (`vfs_file_id`),
  KEY `egw_vfs_directory_name` (`vfs_directory`,`vfs_name`)
) ENGINE=MyISAM AUTO_INCREMENT=5348 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-01-21  9:50:11
