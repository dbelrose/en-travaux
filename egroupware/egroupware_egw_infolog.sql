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
-- Table structure for table `egw_infolog`
--

DROP TABLE IF EXISTS `egw_infolog`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `egw_infolog` (
  `info_id` int(11) NOT NULL AUTO_INCREMENT,
  `info_type` varchar(40) NOT NULL DEFAULT 'task',
  `info_from` varchar(255) DEFAULT NULL,
  `info_addr` varchar(255) DEFAULT NULL,
  `info_subject` varchar(255) DEFAULT NULL,
  `info_des` text,
  `info_owner` int(11) NOT NULL DEFAULT '0',
  `info_responsible` varchar(255) NOT NULL DEFAULT '0',
  `info_access` varchar(10) DEFAULT 'public',
  `info_cat` int(11) NOT NULL DEFAULT '0',
  `info_datemodified` bigint(20) NOT NULL DEFAULT '0',
  `info_startdate` bigint(20) NOT NULL DEFAULT '0',
  `info_enddate` bigint(20) NOT NULL DEFAULT '0',
  `info_id_parent` int(11) NOT NULL DEFAULT '0',
  `info_planned_time` int(11) NOT NULL DEFAULT '0',
  `info_used_time` int(11) NOT NULL DEFAULT '0',
  `info_status` varchar(40) DEFAULT 'done',
  `info_confirm` varchar(10) DEFAULT 'not',
  `info_modifier` int(11) NOT NULL DEFAULT '0',
  `info_link_id` int(11) NOT NULL DEFAULT '0',
  `info_priority` smallint(6) DEFAULT '1',
  `pl_id` int(11) DEFAULT NULL,
  `info_price` double DEFAULT NULL,
  `info_percent` smallint(6) DEFAULT '0',
  `info_datecompleted` bigint(20) DEFAULT NULL,
  `info_location` varchar(255) DEFAULT NULL,
  `info_custom_from` tinyint(4) DEFAULT NULL,
  `info_uid` varchar(255) DEFAULT NULL,
  `info_replanned_time` int(11) NOT NULL DEFAULT '0',
  PRIMARY KEY (`info_id`),
  KEY `info_owner` (`info_owner`,`info_responsible`,`info_status`,`info_startdate`),
  KEY `info_id_parent` (`info_id_parent`,`info_owner`,`info_responsible`,`info_status`,`info_startdate`)
) ENGINE=MyISAM AUTO_INCREMENT=93211 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-08-07  7:59:33
