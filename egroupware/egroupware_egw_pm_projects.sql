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
-- Table structure for table `egw_pm_projects`
--

DROP TABLE IF EXISTS `egw_pm_projects`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `egw_pm_projects` (
  `pm_id` int(11) NOT NULL AUTO_INCREMENT,
  `pm_number` varchar(64) NOT NULL DEFAULT '',
  `pm_title` varchar(255) NOT NULL DEFAULT '',
  `pm_description` text,
  `pm_creator` int(11) NOT NULL DEFAULT '0',
  `pm_created` bigint(20) NOT NULL DEFAULT '0',
  `pm_modifier` int(11) DEFAULT NULL,
  `pm_modified` bigint(20) DEFAULT NULL,
  `pm_planned_start` bigint(20) DEFAULT NULL,
  `pm_planned_end` bigint(20) DEFAULT NULL,
  `pm_real_start` bigint(20) DEFAULT NULL,
  `pm_real_end` bigint(20) DEFAULT NULL,
  `cat_id` int(11) DEFAULT '0',
  `pm_access` varchar(7) DEFAULT 'public',
  `pm_priority` smallint(6) DEFAULT '1',
  `pm_status` varchar(9) DEFAULT 'active',
  `pm_completion` smallint(6) DEFAULT '0',
  `pm_used_time` int(11) DEFAULT NULL,
  `pm_planned_time` int(11) DEFAULT NULL,
  `pm_used_budget` decimal(20,2) DEFAULT NULL,
  `pm_planned_budget` decimal(20,2) DEFAULT NULL,
  `pm_overwrite` int(11) DEFAULT '0',
  `pm_accounting_type` varchar(10) DEFAULT 'times',
  `pm_replanned_time` int(11) DEFAULT NULL,
  PRIMARY KEY (`pm_id`),
  UNIQUE KEY `egw_pm_projects_number` (`pm_number`),
  KEY `egw_pm_projects_title` (`pm_title`)
) ENGINE=MyISAM AUTO_INCREMENT=849 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-09-23 13:36:05
