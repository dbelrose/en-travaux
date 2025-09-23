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
-- Table structure for table `phpgw_p_projects`
--

DROP TABLE IF EXISTS `phpgw_p_projects`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `phpgw_p_projects` (
  `project_id` int(11) NOT NULL AUTO_INCREMENT,
  `p_number` varchar(255) NOT NULL DEFAULT '',
  `owner` int(11) NOT NULL DEFAULT '0',
  `access` varchar(7) DEFAULT NULL,
  `entry_date` int(11) NOT NULL DEFAULT '0',
  `start_date` int(11) NOT NULL DEFAULT '0',
  `end_date` int(11) NOT NULL DEFAULT '0',
  `coordinator` int(11) NOT NULL DEFAULT '0',
  `customer` int(11) NOT NULL DEFAULT '0',
  `status` varchar(9) NOT NULL DEFAULT 'active',
  `descr` text,
  `title` varchar(255) NOT NULL DEFAULT '',
  `budget` decimal(20,2) NOT NULL DEFAULT '0.00',
  `category` int(11) NOT NULL DEFAULT '0',
  `parent` int(11) NOT NULL DEFAULT '0',
  `time_planned` int(11) NOT NULL DEFAULT '0',
  `date_created` int(11) NOT NULL DEFAULT '0',
  `processor` int(11) NOT NULL DEFAULT '0',
  `investment_nr` varchar(50) DEFAULT NULL,
  `main` int(11) NOT NULL DEFAULT '0',
  `level` int(11) NOT NULL DEFAULT '0',
  `previous` int(11) NOT NULL DEFAULT '0',
  `customer_nr` varchar(50) DEFAULT NULL,
  `reference` varchar(255) DEFAULT NULL,
  `url` varchar(255) DEFAULT NULL,
  `result` text,
  `test` text,
  `quality` text,
  `accounting` varchar(8) DEFAULT NULL,
  `acc_factor` decimal(20,2) NOT NULL DEFAULT '0.00',
  `billable` char(1) NOT NULL DEFAULT 'N',
  `psdate` int(11) NOT NULL DEFAULT '0',
  `pedate` int(11) NOT NULL DEFAULT '0',
  `priority` smallint(6) DEFAULT '0',
  `discount` decimal(20,2) DEFAULT '0.00',
  `e_budget` decimal(20,2) DEFAULT '0.00',
  `inv_method` text,
  `acc_factor_d` decimal(20,2) DEFAULT '0.00',
  `discount_type` varchar(7) DEFAULT NULL,
  PRIMARY KEY (`project_id`)
) ENGINE=MyISAM AUTO_INCREMENT=213 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-09-23 13:39:36
