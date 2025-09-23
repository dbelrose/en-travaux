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
-- Table structure for table `egw_tracker`
--

DROP TABLE IF EXISTS `egw_tracker`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `egw_tracker` (
  `tr_id` int(11) NOT NULL AUTO_INCREMENT,
  `tr_summary` varchar(80) NOT NULL,
  `tr_tracker` int(11) NOT NULL,
  `cat_id` int(11) DEFAULT NULL,
  `tr_version` int(11) DEFAULT NULL,
  `tr_status` int(11) DEFAULT '-100',
  `tr_description` text,
  `tr_private` smallint(6) DEFAULT '0',
  `tr_budget` decimal(20,2) DEFAULT NULL,
  `tr_completion` smallint(6) DEFAULT '0',
  `tr_creator` int(11) NOT NULL,
  `tr_created` bigint(20) NOT NULL,
  `tr_modifier` int(11) DEFAULT NULL,
  `tr_modified` bigint(20) DEFAULT NULL,
  `tr_closed` bigint(20) DEFAULT NULL,
  `tr_priority` smallint(6) DEFAULT '5',
  `tr_resolution` varchar(1) DEFAULT '',
  `tr_cc` text,
  `tr_group` int(11) DEFAULT NULL,
  `tr_edit_mode` varchar(5) DEFAULT 'ascii',
  `tr_seen` text,
  PRIMARY KEY (`tr_id`),
  KEY `egw_tracker_tr_summary` (`tr_summary`),
  KEY `egw_tracker_tr_tracker` (`tr_tracker`),
  KEY `egw_tracker_tr_version` (`tr_version`),
  KEY `egw_tracker_tr_status` (`tr_status`),
  KEY `egw_tracker_tr_group` (`tr_group`),
  KEY `egw_tracker_cat_id_tr_status_tr_assigned` (`cat_id`,`tr_status`)
) ENGINE=MyISAM AUTO_INCREMENT=1489 DEFAULT CHARSET=latin1;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-09-23 13:34:45
