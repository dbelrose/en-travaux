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
-- Table structure for table `phpgw_comic_data`
--

DROP TABLE IF EXISTS `phpgw_comic_data`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `phpgw_comic_data` (
  `data_id` int(11) NOT NULL AUTO_INCREMENT,
  `data_enabled` char(1) NOT NULL DEFAULT 'T',
  `data_name` varchar(25) NOT NULL DEFAULT '',
  `data_author` varchar(128) NOT NULL DEFAULT '',
  `data_title` varchar(255) NOT NULL DEFAULT '',
  `data_prefix` varchar(25) NOT NULL DEFAULT '',
  `data_date` int(11) NOT NULL DEFAULT '0',
  `data_comicid` int(11) NOT NULL DEFAULT '0',
  `data_linkurl` varchar(255) NOT NULL DEFAULT '',
  `data_baseurl` varchar(255) NOT NULL DEFAULT '',
  `data_parseurl` varchar(255) NOT NULL DEFAULT '',
  `data_parsexpr` varchar(255) NOT NULL DEFAULT '',
  `data_imageurl` varchar(255) NOT NULL DEFAULT '',
  `data_pubdays` varchar(25) NOT NULL DEFAULT 'Su:Mo:Tu:We:Th:Fr:Sa',
  `data_parser` varchar(32) NOT NULL DEFAULT 'None',
  `data_class` varchar(32) NOT NULL DEFAULT 'General',
  `data_censorlvl` smallint(6) NOT NULL DEFAULT '0',
  `data_resolve` varchar(32) NOT NULL DEFAULT 'Remote',
  `data_daysold` int(11) NOT NULL DEFAULT '0',
  `data_width` int(11) NOT NULL DEFAULT '0',
  `data_swidth` int(11) NOT NULL DEFAULT '0',
  PRIMARY KEY (`data_id`)
) ENGINE=MyISAM AUTO_INCREMENT=123 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-09-23 13:37:17
