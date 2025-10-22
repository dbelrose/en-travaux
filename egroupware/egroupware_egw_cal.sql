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
-- Table structure for table `egw_cal`
--

DROP TABLE IF EXISTS `egw_cal`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `egw_cal` (
  `cal_id` int(11) NOT NULL AUTO_INCREMENT,
  `cal_uid` varchar(255) NOT NULL DEFAULT '',
  `cal_owner` int(11) NOT NULL DEFAULT '0',
  `cal_category` varchar(30) DEFAULT NULL,
  `cal_modified` bigint(20) DEFAULT NULL,
  `cal_priority` smallint(6) NOT NULL DEFAULT '2',
  `cal_public` smallint(6) NOT NULL DEFAULT '1',
  `cal_title` varchar(255) NOT NULL DEFAULT '1',
  `cal_description` text,
  `cal_location` varchar(255) DEFAULT NULL,
  `cal_reference` int(11) NOT NULL DEFAULT '0',
  `cal_modifier` int(11) DEFAULT NULL,
  `cal_non_blocking` smallint(6) DEFAULT '0',
  `cal_special` smallint(6) DEFAULT '0',
  `cal_etag` int(11) DEFAULT '0',
  PRIMARY KEY (`cal_id`)
) ENGINE=MyISAM AUTO_INCREMENT=403239 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-10-22 10:58:56
