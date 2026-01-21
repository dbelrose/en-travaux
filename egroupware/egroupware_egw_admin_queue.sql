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
-- Table structure for table `egw_admin_queue`
--

DROP TABLE IF EXISTS `egw_admin_queue`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `egw_admin_queue` (
  `cmd_id` int(11) NOT NULL AUTO_INCREMENT,
  `cmd_uid` varchar(255) NOT NULL,
  `cmd_creator` int(11) NOT NULL,
  `cmd_creator_email` varchar(128) NOT NULL,
  `cmd_created` bigint(20) NOT NULL,
  `cmd_type` varchar(32) NOT NULL DEFAULT 'admin_cmd',
  `cmd_status` tinyint(4) DEFAULT NULL,
  `cmd_scheduled` bigint(20) DEFAULT NULL,
  `cmd_modified` bigint(20) DEFAULT NULL,
  `cmd_modifier` int(11) DEFAULT NULL,
  `cmd_modifier_email` varchar(128) DEFAULT NULL,
  `cmd_error` varchar(255) DEFAULT NULL,
  `cmd_errno` int(11) DEFAULT NULL,
  `cmd_requested` int(11) DEFAULT NULL,
  `cmd_requested_email` varchar(128) DEFAULT NULL,
  `cmd_comment` varchar(255) DEFAULT NULL,
  `cmd_data` longblob,
  `remote_id` int(11) DEFAULT NULL,
  PRIMARY KEY (`cmd_id`),
  UNIQUE KEY `egw_admin_queue_cmd_uid` (`cmd_uid`),
  KEY `egw_admin_queue_cmd_status` (`cmd_status`),
  KEY `egw_admin_queue_cmd_scheduled` (`cmd_scheduled`)
) ENGINE=MyISAM DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-01-21  9:53:00
