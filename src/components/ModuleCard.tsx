import { motion } from "framer-motion";
import { useApp, type ModuleDef } from "../store";

const cardVariants = {
  hidden: { opacity: 0, y: 14, scale: 0.97 },
  visible: { opacity: 1, y: 0, scale: 1 },
};

export default function ModuleCard({
  def,
  favorite = false,
  index = 0,
}: {
  def: ModuleDef;
  favorite?: boolean;
  index?: number;
}) {
  const openToolDialog = useApp((s) => s.openToolDialog);
  const toggleFavorite = useApp((s) => s.toggleFavorite);
  const [label, status, icon, desc, key] = def;

  return (
    <motion.div
      className="card"
      variants={cardVariants}
      whileHover={{ y: -4 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
      onClick={() => void openToolDialog(key)}
      data-index={index}
    >
      <div className={`card-chip chip-${status}`}>{icon}</div>
      <div className="card-body">
        <div className="card-title-row">
          <span className="card-title">{label}</span>
          <button
            className={`fav-toggle ${favorite ? "on" : ""}`}
            title={favorite ? "Remove from favorites" : "Add to favorites"}
            onClick={(e) => {
              e.stopPropagation();
              void toggleFavorite(key);
            }}
          >
            {favorite ? "★" : "☆"}
          </button>
          <span className={`status-pill status-${status}`}>{status}</span>
        </div>
        <div className="card-desc">{desc}</div>
      </div>
    </motion.div>
  );
}
