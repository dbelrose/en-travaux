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
-- Table structure for table `egw_kb_articles`
--

DROP TABLE IF EXISTS `egw_kb_articles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `egw_kb_articles` (
  `art_id` int(11) NOT NULL AUTO_INCREMENT,
  `q_id` bigint(20) NOT NULL DEFAULT '0',
  `title` varchar(255) NOT NULL DEFAULT '',
  `topic` varchar(255) NOT NULL DEFAULT '',
  `text` longtext,
  `cat_id` int(11) NOT NULL DEFAULT '0',
  `published` smallint(6) NOT NULL DEFAULT '0',
  `user_id` int(11) NOT NULL DEFAULT '0',
  `views` int(11) NOT NULL DEFAULT '0',
  `created` int(11) DEFAULT NULL,
  `modified` int(11) DEFAULT NULL,
  `modified_user_id` int(11) NOT NULL DEFAULT '0',
  `votes_1` int(11) NOT NULL DEFAULT '0',
  `votes_2` int(11) NOT NULL DEFAULT '0',
  `votes_3` int(11) NOT NULL DEFAULT '0',
  `votes_4` int(11) NOT NULL DEFAULT '0',
  `votes_5` int(11) NOT NULL DEFAULT '0',
  PRIMARY KEY (`art_id`)
) ENGINE=MyISAM AUTO_INCREMENT=54 DEFAULT CHARSET=utf8;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-01-21  9:51:18
