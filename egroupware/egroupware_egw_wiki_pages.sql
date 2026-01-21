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
-- Table structure for table `egw_wiki_pages`
--

DROP TABLE IF EXISTS `egw_wiki_pages`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `egw_wiki_pages` (
  `wiki_id` smallint(6) NOT NULL DEFAULT '0',
  `wiki_name` varchar(80) NOT NULL DEFAULT '',
  `wiki_lang` varchar(5) NOT NULL DEFAULT '',
  `wiki_version` int(11) NOT NULL DEFAULT '1',
  `wiki_time` int(11) DEFAULT NULL,
  `wiki_supercede` int(11) DEFAULT NULL,
  `wiki_readable` int(11) NOT NULL DEFAULT '0',
  `wiki_writable` int(11) NOT NULL DEFAULT '0',
  `wiki_username` varchar(80) DEFAULT NULL,
  `wiki_hostname` varchar(80) NOT NULL DEFAULT '',
  `wiki_comment` varchar(80) NOT NULL DEFAULT '',
  `wiki_title` varchar(80) DEFAULT NULL,
  `wiki_body` longtext,
  PRIMARY KEY (`wiki_id`,`wiki_name`,`wiki_lang`,`wiki_version`),
  KEY `egw_wiki_pages_title` (`wiki_title`),
  FULLTEXT KEY `egw_wiki_pages_body` (`wiki_body`)
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

-- Dump completed on 2026-01-21  9:52:10
